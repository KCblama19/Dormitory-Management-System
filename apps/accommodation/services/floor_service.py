from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max

# Models
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Building,
    Floor,
    Room,
)

# Policies
from apps.core.policies import AccommodationPolicy

# Database locking utilities
from apps.core.db.locking import get_locked_instance

# Application exceptions
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    PermissionDenied,
    NotFoundError,
)


class FloorService:
    """
    Handles floor creation, updates, status transitions, restrictions,
    and bed-configuration overrides.

    Locking contract:

        Building -> Floor -> Room -> BedConfiguration -> Bed

    Existing-floor operations:
        Shared Building -> Exclusive Floor

    Floor creation:
        Exclusive Building -> Shared BedConfiguration

    The exclusive Floor lock coordinates with child operations that
    acquire shared Floor locks before modifying Rooms or Beds.

    PostgreSQL is required for the row-level locking guarantees.
    """

    GENDER_MAPPING = {
        Building.GenderPolicy.MALE_ONLY:
            Floor.GenderConfiguration.MALE,

        Building.GenderPolicy.FEMALE_ONLY:
            Floor.GenderConfiguration.FEMALE,
    }

    # ---------------------------------------------------------
    # LOCKING HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _get_locked_building(
        building,
        *,
        mode="shared",
    ):
        """
        Lock and refresh a Building.

        Existing-floor operations use a shared Building lock.
        Floor creation uses an exclusive Building lock because
        floor-number allocation is Building-wide.
        """

        try:
            return get_locked_instance(
                Building,
                building.pk,
                mode=mode,
            )

        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The requested building could not be found."
            ) from exc

    @classmethod
    def _get_locked_floor(cls, floor):
        """
        Acquire locks in the required hierarchy:

            Building shared -> Floor exclusive

        The Building identifier is read first to determine which
        ancestor must be locked. The Floor is then refreshed after
        acquiring its exclusive lock.

        All operations that modify a Floor must use this helper.
        """

        try:
            building_id = (
                Floor.objects
                .only("building_id")
                .get(pk=floor.pk)
                .building_id
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

        # Compatible with other operations under the same Building,
        # but prevents a Building-level mutation from proceeding.
        cls._get_locked_building(
            Building(pk=building_id),
            mode="shared",
        )

        try:
            locked_floor = get_locked_instance(
                Floor,
                floor.pk,
                mode="exclusive",
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

        # Load related state only after the Floor has been locked.
        # The Building row is already protected by our shared lock.
        locked_floor = (
            Floor.objects
            .select_related(
                "building",
                "building__default_bed_configuration",
                "bed_configuration_override",
            )
            .get(pk=locked_floor.pk)
        )

        return locked_floor

    @staticmethod
    def _get_configuration(configuration):
        """
        Retrieve the current configuration under a shared lock.

        Floor operations only need to inspect or assign configuration
        state. Capacity changes are coordinated by BedConfigurationService,
        which will acquire exclusive locks on dependent Buildings.
        """

        configuration_id = getattr(
            configuration,
            "pk",
            configuration,
        )

        try:
            return get_locked_instance(
                BedConfiguration,
                configuration_id,
                mode="shared",
            )

        except BedConfiguration.DoesNotExist as exc:
            raise NotFoundError(
                "The selected bed configuration could not be found."
            ) from exc

    # ---------------------------------------------------------
    # PERSISTENCE
    # ---------------------------------------------------------

    @staticmethod
    def _save_floor(floor):
        """
        Validate and persist a Floor.

        The nested atomic block creates a savepoint, allowing
        integrity errors to be translated without leaving the
        surrounding service transaction unusable.
        """

        try:
            with transaction.atomic():
                floor.full_clean()
                floor.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The floor could not be saved because it conflicts "
                "with existing accommodation records."
            ) from exc

        return floor

    # ---------------------------------------------------------
    # VALIDATION HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _next_floor_number(building):
        """
        Return the lowest available floor number.

        Existing floor numbers remain reserved, including floors
        that are inactive or under maintenance.

        The caller must hold an exclusive Building lock.
        """

        existing_numbers = set(
            building.floors.values_list(
                "floor_number",
                flat=True,
            )
        )

        for floor_number in range(
            1,
            building.max_floors + 1,
        ):
            if floor_number not in existing_numbers:
                return floor_number

        raise ConflictError(
            "The building has reached its maximum number of floors."
        )

    @staticmethod
    def _validate_gender_configuration(
        building,
        gender_configuration,
    ):
        """
        Validate the floor gender configuration against its Building.

        Floor-level gender configuration is only allowed inside
        mixed-gender buildings.
        """

        if gender_configuration is None:
            return

        if building.gender_policy != Building.GenderPolicy.MIXED:
            raise ValidationError(
                "Floor-level gender configuration is only allowed "
                "in a mixed-gender building."
            )

    @staticmethod
    def _validate_active_configuration(configuration):
        """
        Ensure a configuration is active before assigning it.
        """

        if configuration is None:
            raise ValidationError(
                "A valid bed configuration must be assigned."
            )

        if not configuration.is_active:
            raise ValidationError(
                "An inactive bed configuration cannot be used."
            )

    @classmethod
    def _validate_inherited_room_capacity(
        cls,
        floor,
        configuration,
    ):
        """
        Validate the selected configuration against physical beds
        in Rooms inheriting the Floor configuration.

        The caller must hold:

            Shared Building -> Exclusive Floor

        Room and Bed operations must acquire a shared Floor lock
        before modifying those resources. Consequently, they cannot
        modify descendants while this Floor is exclusively locked.

        Rooms with their own configuration overrides are excluded.
        Physical beds are checked regardless of operational status.
        """

        cls._validate_active_configuration(configuration)

        # The exclusive Floor lock coordinates with RoomService
        # and BedService operations that require a shared Floor lock.
        #
        # Therefore, room creation, room configuration changes,
        # and physical bed changes beneath this Floor cannot proceed
        # concurrently with this validation.
        room_ids = list(
            Room.objects.filter(
                floor_id=floor.pk,
                bed_configuration_override__isnull=True,
            ).values_list(
                "pk",
                flat=True,
            )
        )

        if not room_ids:
            return

        highest_positions = {
            item["room_id"]: item["highest_position"]
            for item in (
                Bed.objects
                .filter(room_id__in=room_ids)
                .values("room_id")
                .annotate(
                    highest_position=Max("position"),
                )
            )
        }

        for room_id, highest_position in highest_positions.items():
            if highest_position > configuration.bed_count:
                raise ConflictError(
                    f"Room ID {room_id} contains a physical bed "
                    f"at position {highest_position}, which exceeds "
                    f"the selected configuration capacity of "
                    f"{configuration.bed_count}."
                )

    # ---------------------------------------------------------
    # CREATE FLOOR
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def create_floor(
        cls,
        *,
        actor,
        building,
        max_rooms_per_floor,
        gender_configuration=None,
        bed_configuration_override=None,
    ):
        """
        Create a Floor inside a Building.

        Floor creation takes an exclusive Building lock because
        floor-number allocation is Building-wide.

        Restriction fields are intentionally excluded. Restrictions
        must be applied through set_restriction(), which performs
        the dedicated restriction authorization check.
        """

        building = cls._get_locked_building(
            building,
            mode="exclusive",
        )

        if not AccommodationPolicy.can_create_floor(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to create floors "
                "in this building."
            )

        if not building.is_active:
            raise ValidationError(
                "Cannot create a floor in an inactive building."
            )

        floor_number = cls._next_floor_number(building)

        cls._validate_gender_configuration(
            building,
            gender_configuration,
        )

        if bed_configuration_override is not None:
            configuration = cls._get_configuration(
                bed_configuration_override
            )
        else:
            configuration = cls._get_configuration(
                building.default_bed_configuration
            )

        cls._validate_active_configuration(configuration)

        floor = Floor(
            building=building,
            floor_number=floor_number,
            max_rooms_per_floor=max_rooms_per_floor,
            gender_configuration=gender_configuration,
            bed_configuration_override=(
                configuration
                if bed_configuration_override is not None
                else None
            ),
        )

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # UPDATE FLOOR
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def update_floor(
        cls,
        *,
        actor,
        floor,
        **changes,
    ):
        """
        Update permitted Floor fields.

        Restriction fields are deliberately excluded. They must be
        changed through the dedicated restriction operations.

        The exclusive Floor lock coordinates with child operations
        that acquire shared Floor locks before modifying Rooms or Beds.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_update_floor(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to update floors "
                "in this building."
            )

        allowed_fields = {
            "max_rooms_per_floor",
            "gender_configuration",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            field = sorted(unknown_fields)[0]

            raise ValidationError(
                f"'{field}' cannot be edited."
            )

        if "max_rooms_per_floor" in changes:
            new_limit = changes["max_rooms_per_floor"]

            if new_limit is None or new_limit < 1:
                raise ValidationError(
                    "Maximum rooms per floor must be at least one."
                )

            highest_position = floor.rooms.aggregate(
                highest_position=Max("position"),
            )["highest_position"]

            if (
                highest_position is not None
                and highest_position > new_limit
            ):
                raise ConflictError(
                    "Maximum rooms per floor cannot be lower than "
                    "the highest existing room position."
                )

        if "gender_configuration" in changes:
            cls._validate_gender_configuration(
                floor.building,
                changes["gender_configuration"],
            )

        for field, value in changes.items():
            setattr(floor, field, value)

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # FLOOR STATUS TRANSITIONS
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def activate_floor(cls, actor, floor):
        """
        Activate a Floor.

        The parent Building must be active.

        This method currently permits activation from Maintenance.
        If the intended workflow requires a separate maintenance
        release operation, that will need to be defined explicitly.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_activate_floor(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this floor."
            )

        if not floor.building.is_active:
            raise ValidationError(
                "Cannot activate a floor inside an inactive building."
            )

        floor.status = Floor.FloorStatus.ACTIVE

        return cls._save_floor(floor)

    @classmethod
    @transaction.atomic
    def deactivate_floor(cls, actor, floor):
        """
        Deactivate a Floor.

        Occupancy validation remains deferred until AssignmentService
        is implemented.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_deactivate_floor(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate this floor."
            )

        floor.status = Floor.FloorStatus.INACTIVE

        return cls._save_floor(floor)

    @classmethod
    @transaction.atomic
    def set_maintenance(cls, actor, floor):
        """
        Set the Floor operational status to Maintenance.

        Occupancy-dependent restrictions remain deferred until
        AssignmentService is implemented.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_set_floor_maintenance(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to set this floor "
                "for maintenance."
            )

        floor.status = Floor.FloorStatus.MAINTENANCE

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # FLOOR RESTRICTIONS
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def set_restriction(
        cls,
        actor,
        floor,
        note=None,
    ):
        """
        Restrict a Floor and record the reason.

        Restriction changes use an exclusive Floor lock so that
        room and bed operations following the shared-Floor protocol
        coordinate with the restriction change.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_set_floor_restriction(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to restrict this floor."
            )

        if not note or not note.strip():
            raise ValidationError(
                "A restriction note is required."
            )

        floor.is_restricted = True
        floor.restriction_note = note.strip()

        return cls._save_floor(floor)

    @classmethod
    @transaction.atomic
    def remove_restriction(cls, actor, floor):
        """
        Remove a Floor restriction and clear its restriction note.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_remove_floor_restriction(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to remove this "
                "floor restriction."
            )

        floor.is_restricted = False
        floor.restriction_note = None

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # FLOOR BED CONFIGURATION
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def set_bed_configuration_override(
        cls,
        actor,
        floor,
        configuration,
    ):
        """
        Assign a Floor-level bed configuration override.

        The Floor is exclusively locked before validating its
        inheriting Rooms. Child operations must acquire shared
        Floor locks, preventing concurrent bed changes beneath
        this Floor while capacity is being checked.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_change_floor_bed_configuration(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You are not allowed to change this floor's "
                "bed configuration."
            )

        selected_configuration = cls._get_configuration(
            configuration
        )

        cls._validate_inherited_room_capacity(
            floor,
            selected_configuration,
        )

        floor.bed_configuration_override = selected_configuration

        return cls._save_floor(floor)

    @classmethod
    @transaction.atomic
    def remove_bed_configuration_override(
        cls,
        actor,
        floor,
    ):
        """
        Remove the Floor override and restore the Building default.

        The Building default must be active and capable of
        accommodating every physical bed in Rooms inheriting
        the Floor configuration.

        Rooms with their own configuration overrides are excluded.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_change_floor_bed_configuration(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You are not allowed to remove this floor's "
                "bed configuration override."
            )

        inherited_configuration = cls._get_configuration(
            floor.building.default_bed_configuration
        )

        cls._validate_inherited_room_capacity(
            floor,
            inherited_configuration,
        )

        floor.bed_configuration_override = None

        return cls._save_floor(floor)