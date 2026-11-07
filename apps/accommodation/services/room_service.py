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
    PermissionDenied,
    ConflictError,
    NotFoundError,
)


class RoomService:
    """
    Handles room creation, updates, and bed-configuration inheritance.

    Configuration inheritance:

        Room override -> Floor override -> Building default

    Locking contract:

        Building -> Floor -> Room -> BedConfiguration -> Bed

    Existing room operations:
        Building shared -> Floor shared -> Room exclusive

    Room creation:
        Building shared -> Floor exclusive

    Room creation requires an exclusive Floor lock because room
    positions are allocated within that Floor.

    Ordinary operations on different Rooms can proceed concurrently
    because they acquire compatible shared locks on their ancestors
    and exclusive locks only on their own Room.
    """

    # ---------------------------------------------------------
    # LOCKING HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _get_locked_building(
        building_id,
        *,
        mode="shared",
    ):
        """
        Lock and refresh the Building.

        Existing room operations use a shared Building lock.
        Room creation also uses a shared Building lock because
        its position allocation is scoped to the Floor.

        Building-level changes acquire an exclusive Building lock
        through BuildingService.
        """

        try:
            return get_locked_instance(
                Building,
                building_id,
                mode=mode,
            )

        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The requested building could not be found."
            ) from exc

    @classmethod
    def _get_locked_floor(
        cls,
        floor_id,
        *,
        mode="shared",
    ):
        """
        Lock and refresh the Floor using the hierarchy:

            Building shared -> Floor lock

        Existing room operations use a shared Floor lock.

        Room creation uses an exclusive Floor lock to coordinate
        room-position allocation.

        The Building shared lock prevents BuildingService from
        changing the parent while this operation is in progress.
        """

        # Read the parent identifier before acquiring locks.
        # The Floor's parent relationship is immutable through
        # the accommodation service operations.
        try:
            building_id = (
                Floor.objects
                .only("building_id")
                .get(pk=floor_id)
                .building_id
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

        cls._get_locked_building(
            building_id,
            mode="shared",
        )

        try:
            locked_floor = get_locked_instance(
                Floor,
                floor_id,
                mode=mode,
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

        # Refresh related configuration after the Floor lock.
        # Building and Floor configuration changes must follow
        # the same ancestor-locking contract.
        return (
            Floor.objects
            .select_related(
                "building",
                "building__default_bed_configuration",
                "bed_configuration_override",
            )
            .get(pk=locked_floor.pk)
        )

    @classmethod
    def _get_locked_room(cls, room_id):
        """
        Lock the ancestors shared and the target Room exclusively.

        Lock order:

            Building shared
            Floor shared
            Room exclusive

        This permits operations on different Rooms under the
        same Floor to proceed concurrently.

        The returned Floor is refreshed after the locks are held.
        """

        try:
            floor_id = (
                Room.objects
                .only("floor_id")
                .get(pk=room_id)
                .floor_id
            )

        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The requested room could not be found."
            ) from exc

        floor = cls._get_locked_floor(
            floor_id,
            mode="shared",
        )

        try:
            locked_room = get_locked_instance(
                Room,
                room_id,
                mode="exclusive",
            )

        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The requested room could not be found."
            ) from exc

        if locked_room.floor_id != floor.pk:
            raise ConflictError(
                "The room's floor changed while the operation "
                "was being processed."
            )

        # Refresh configuration inheritance after locking the Room.
        room = (
            Room.objects
            .select_related(
                "floor",
                "floor__building",
                "floor__building__default_bed_configuration",
                "floor__bed_configuration_override",
                "bed_configuration_override",
            )
            .get(pk=locked_room.pk)
        )

        return room, floor

    @staticmethod
    def _get_configuration(configuration):
        """
        Retrieve the current BedConfiguration under a shared lock.

        Room operations inspect configuration state but do not
        change configuration capacity.

        BedConfigurationService will acquire exclusive locks on
        dependent Buildings before changing configuration capacity.
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
    # POSITION ALLOCATION
    # ---------------------------------------------------------

    @staticmethod
    def _next_room_position(floor):
        """
        Return the first available Room position.

        Positions are reused when gaps exist.

        The caller must hold an exclusive Floor lock.
        """

        occupied_positions = set(
            floor.rooms.values_list(
                "position",
                flat=True,
            )
        )

        for position in range(
            1,
            floor.max_rooms_per_floor + 1,
        ):
            if position not in occupied_positions:
                return position

        raise ConflictError(
            "This floor has reached its maximum room capacity."
        )

    # ---------------------------------------------------------
    # CONFIGURATION RESOLUTION
    # ---------------------------------------------------------

    @classmethod
    def _resolve_inherited_configuration(cls, floor):
        """
        Resolve the effective configuration without a Room override.

        Inheritance:

            Floor override -> Building default

        The configuration is retrieved under a shared lock.
        """

        configuration = (
            floor.bed_configuration_override
            or floor.building.default_bed_configuration
        )

        return cls._get_configuration(configuration)

    @staticmethod
    def _validate_configuration_capacity(
        room,
        configuration,
    ):
        """
        Ensure a configuration accommodates every physical bed.

        The highest existing position is checked instead of the
        number of Bed records.

        Maintenance and out-of-service beds are included because
        they remain physically present in the Room.

        The caller must hold an exclusive Room lock.
        """

        if configuration is None:
            if Bed.objects.for_room(room).exists():
                raise ConflictError(
                    "The room has existing physical beds and cannot "
                    "use an empty bed configuration."
                )

            raise ValidationError(
                "A valid bed configuration must be assigned "
                "to the room."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The selected bed configuration is inactive."
            )

        highest_position = (
            Bed.objects
            .for_room(room)
            .aggregate(
                highest_position=Max("position"),
            )["highest_position"]
        )

        if (
            highest_position is not None
            and highest_position > configuration.bed_count
        ):
            raise ConflictError(
                "The selected configuration cannot accommodate "
                "the existing physical bed positions."
            )

    # ---------------------------------------------------------
    # PERSISTENCE
    # ---------------------------------------------------------

    @staticmethod
    def _save_room(room):
        """
        Validate and persist a Room.

        The nested atomic block creates a savepoint. Database
        integrity errors can therefore be translated without
        leaving the surrounding service transaction unusable.
        """

        try:
            with transaction.atomic():
                room.full_clean()
                room.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The room could not be saved because it conflicts "
                "with an existing accommodation record."
            ) from exc

        return room

    # ---------------------------------------------------------
    # FLOOR VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_floor_for_room_creation(floor):
        """
        Ensure the Floor is operational before creating a Room.
        """

        if not floor.is_active:
            raise ValidationError(
                "Rooms cannot be created on an inactive floor."
            )

        if floor.status != Floor.FloorStatus.ACTIVE:
            raise ValidationError(
                "Rooms can only be created on active floors."
            )

    # ---------------------------------------------------------
    # ROOM CREATION
    # ---------------------------------------------------------


    @staticmethod
    @transaction.atomic
    def create_room(
        *,
        actor,
        floor,
        bed_configuration_override=None,
    ) -> Room:
        """
        Create a room and generate its physical beds.

        Room creation and bed generation share one transaction. If
        generation fails, the room creation is rolled back as well.
        """

        # Room positions are allocated per floor, so this operation
        # requires an exclusive floor lock.
        locked_floor = RoomService._get_locked_floor(
            floor.pk,
            mode="exclusive",
        )

        if not AccommodationPolicy.can_create_room(
            actor,
            locked_floor,
        ):
            raise PermissionDenied(
                "You do not have permission to create rooms "
                "on this floor."
            )

        RoomService._validate_floor_for_room_creation(
            locked_floor
        )

        position = RoomService._next_room_position(
            locked_floor
        )

        room = Room(
            floor=locked_floor,
            position=position,
        )

        if bed_configuration_override is not None:
            configuration = RoomService._get_configuration(
                bed_configuration_override
            )
            room.bed_configuration_override = configuration
        else:
            # Resolve the inherited configuration explicitly.
            configuration = (
                RoomService._resolve_inherited_configuration(
                    locked_floor
                )
            )

        RoomService._validate_configuration_capacity(
            room,
            configuration,
        )

        room = RoomService._save_room(room)

        # Import locally to avoid a circular dependency between the
        # RoomService and BedService modules.
        from apps.accommodation.services.bed_service import (
            BedService,
        )

        # This runs inside the same outer transaction. A permission,
        # validation, or persistence failure rolls back the room too.
        BedService.generate_beds(
            actor=actor,
            room=room,
        )

        return room


    # ---------------------------------------------------------
    # ROOM UPDATE
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def update_room(
        cls,
        *,
        actor,
        room,
        bed_configuration_override=None,
    ):
        """
        Update the Room's editable configuration.

        None means no configuration change.

        Removing an override remains a dedicated operation.

        Lock order:

            Building shared -> Floor shared -> Room exclusive
            -> Configuration shared
        """

        locked_room, _ = cls._get_locked_room(
            room.pk
        )

        if not AccommodationPolicy.can_update_room(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to update this room."
            )

        if bed_configuration_override is not None:
            configuration = cls._get_configuration(
                bed_configuration_override
            )

            cls._validate_configuration_capacity(
                locked_room,
                configuration,
            )

            locked_room.bed_configuration_override = configuration

            cls._save_room(locked_room)

        return locked_room

    # ---------------------------------------------------------
    # BED CONFIGURATION OVERRIDE
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def set_bed_configuration_override(
        cls,
        *,
        actor,
        room,
        configuration,
    ):
        """
        Assign a Room-level bed configuration override.

        The Room is exclusively locked before validating existing
        physical beds or changing the override.
        """

        locked_room, _ = cls._get_locked_room(
            room.pk
        )

        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to manage this room's operations."
            )

        selected_configuration = cls._get_configuration(
            configuration
        )

        cls._validate_configuration_capacity(
            locked_room,
            selected_configuration,
        )

        locked_room.bed_configuration_override = (
            selected_configuration
        )

        return cls._save_room(locked_room)

    @classmethod
    @transaction.atomic
    def remove_bed_configuration_override(
        cls,
        *,
        actor,
        room,
    ):
        """
        Remove the Room override and restore inherited configuration.

        Inheritance:

            Floor override -> Building default

        The inherited configuration must accommodate every existing
        physical bed position before the override can be removed.
        """

        locked_room, _ = cls._get_locked_room(
            room.pk
        )

        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to manage this room's operations."
            )

        inherited_configuration = (
            cls._resolve_inherited_configuration(
                locked_room.floor
            )
        )

        cls._validate_configuration_capacity(
            locked_room,
            inherited_configuration,
        )

        locked_room.bed_configuration_override = None

        return cls._save_room(locked_room)
