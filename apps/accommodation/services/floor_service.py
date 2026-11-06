
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

    Floor-level bed configuration inheritance:

        Floor override → Building default

    Rooms with their own configuration overrides are excluded when
    validating a Floor configuration change.
    """

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _next_floor_number(building):
        """
        Return the lowest available floor number.

        Existing floor numbers are reserved even when their floors
        are inactive or under maintenance.

        The Building must already be locked by the calling transaction.
        """

        existing_numbers = set(
            building.floors.values_list(
                "floor_number",
                flat=True,
            )
        )

        for floor_number in range(1, building.max_floors + 1):
            if floor_number not in existing_numbers:
                return floor_number

        raise ConflictError(
            "The building has reached its maximum number of floors."
        )

    @staticmethod
    def _get_locked_building(building):
        """
        Retrieve and lock the latest Building record.

        The Building lock coordinates floor-number allocation and
        protects operations that depend on its current state.
        """

        try:
            return (
                Building.objects
                .select_for_update()
                .with_configuration()
                .get(pk=building.pk)
            )

        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The requested building could not be found."
            ) from exc

    @staticmethod
    def _get_locked_floor(floor):
        """
        Retrieve and lock the latest Floor record.

        Related Building and configuration records are loaded using
        the existing FloorQuerySet methods.
        """

        try:
            return (
                Floor.objects
                .select_for_update()
                .with_building()
                .with_configuration()
                .get(pk=floor.pk)
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

    @staticmethod
    def _get_configuration(configuration):
        """
        Retrieve and lock the latest BedConfiguration record.

        This avoids relying on potentially stale configuration instances
        supplied by callers.
        """

        configuration_id = getattr(
            configuration,
            "pk",
            configuration,
        )

        try:
            return (
                BedConfiguration.objects
                .select_for_update()
                .get(pk=configuration_id)
            )

        except BedConfiguration.DoesNotExist as exc:
            raise NotFoundError(
                "The selected bed configuration could not be found."
            ) from exc

    @staticmethod
    def _save_floor(floor):
        """
        Validate and persist a Floor.

        A nested atomic block creates a savepoint. This allows database
        integrity errors to be translated safely without leaving the
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

    @staticmethod
    def _validate_gender_configuration(building, gender_configuration):
        """
        Validate floor-level gender configuration against the
        Building's gender policy.

        Floor-level gender configuration is only permitted inside
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
    def _validate_inherited_room_capacity(cls, floor, configuration):
        """
        Ensure a Floor configuration can accommodate the physical beds
        in every Room that inherits the Floor's configuration.

        Rooms with their own room-level override are deliberately excluded.

        The Floor is expected to be locked before this method is called.
        Room rows are locked before checking their Bed records. This
        coordinates with BedService operations that lock Floor → Room
        before creating or changing physical beds.

        The highest physical Bed position is checked, not the number
        of Bed records. Maintenance and out-of-service beds are included.
        """

        cls._validate_active_configuration(configuration)

        # Lock only rooms that inherit the Floor configuration.
        inheriting_rooms = list(
            Room.objects
            .select_for_update()
            .filter(
                floor=floor,
                bed_configuration_override__isnull=True,
            )
            .only("pk")
        )

        if not inheriting_rooms:
            return

        room_ids = [room.pk for room in inheriting_rooms]

        # Aggregate physical bed positions for all affected rooms.
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

        for room in inheriting_rooms:
            highest_position = highest_positions.get(room.pk)

            if (
                highest_position is not None
                and highest_position > configuration.bed_count
            ):
                raise ConflictError(
                    f"Room ID {room.pk} contains a physical bed at "
                    f"position {highest_position}, which exceeds the "
                    f"selected configuration capacity of "
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
        restriction_note=None,
        is_restricted=False,
    ):
        """
        Create a Floor inside a Building.

        The Building is locked before calculating the next floor number.
        This prevents concurrent requests from selecting the same number.

        The effective configuration must also be active, whether it comes
        from a Floor override or the Building default.
        """

        building = cls._get_locked_building(building)

        if not AccommodationPolicy.can_create_floor(actor, building):
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
            restriction_note=restriction_note,
            is_restricted=is_restricted,
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

        Fields affecting relationships or system-managed properties
        must be changed through dedicated service methods.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_update_floor(actor, floor):
            raise PermissionDenied(
                "You do not have permission to update floors "
                "in this building."
            )

        allowed_fields = {
            "max_rooms_per_floor",
            "gender_configuration",
            "restriction_note",
            "is_restricted",
        }

        # Reject fields that are not explicitly editable.
        for field in changes:
            if field not in allowed_fields:
                raise ValidationError(
                    f"'{field}' cannot be edited."
                )

        # Check the highest occupied room position rather than the
        # number of rooms. Room positions can contain gaps.
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
    # ACTIVATE FLOOR
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def activate_floor(cls, actor, floor):
        """
        Activate a Floor.

        A Floor cannot be activated while its parent Building is inactive.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_activate_floor(actor, floor):
            raise PermissionDenied(
                "You do not have permission to activate this floor."
            )

        if not floor.building.is_active:
            raise ValidationError(
                "Cannot activate a floor inside an inactive building."
            )

        floor.status = Floor.FloorStatus.ACTIVE

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # DEACTIVATE FLOOR
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def deactivate_floor(cls, actor, floor):
        """
        Deactivate a Floor.

        Occupancy validation is intentionally deferred until the
        Assignment model is implemented.
        """

        floor = cls._get_locked_floor(floor)

        if not AccommodationPolicy.can_deactivate_floor(actor, floor):
            raise PermissionDenied(
                "You do not have permission to deactivate this floor."
            )

        floor.status = Floor.FloorStatus.INACTIVE

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # SET FLOOR MAINTENANCE
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def set_maintenance(cls, actor, floor):
        """
        Set a Floor's operational status to maintenance.

        Occupancy-dependent restrictions will be added when the
        Assignment model is available.
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
    # SET FLOOR RESTRICTION
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
        Restrict a Floor and record the reason for the restriction.
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

    # ---------------------------------------------------------
    # REMOVE FLOOR RESTRICTION
    # ---------------------------------------------------------

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
    # SET BED CONFIGURATION OVERRIDE
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

        Before applying the override, validate every Room that inherits
        the Floor configuration. Room-level overrides remain unaffected.
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

        selected_configuration = cls._get_configuration(configuration)

        cls._validate_inherited_room_capacity(
            floor,
            selected_configuration,
        )

        floor.bed_configuration_override = selected_configuration

        return cls._save_floor(floor)

    # ---------------------------------------------------------
    # REMOVE BED CONFIGURATION OVERRIDE
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def remove_bed_configuration_override(cls, actor, floor):
        """
        Remove the Floor-level override and restore the Building default.

        The Building default must be active and capable of accommodating
        every physical bed in Rooms that inherit the Floor configuration.

        Rooms with their own overrides are not affected.
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