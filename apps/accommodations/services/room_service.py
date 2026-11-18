from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.assignments.services.commitment_queries import (
    beds_requiring_valid_position,
)

# Models
from apps.accommodations.models import (
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

    Locking hierarchy:

        Building -> Floor -> Room -> BedConfiguration -> Bed

    Existing room operations:

        Building (shared) -> Floor (shared) -> Room (exclusive)

    Room creation:

        Building (shared) -> Floor (exclusive)

    The exclusive Floor lock coordinates room-position allocation.
    Once a Room exists, ordinary operations lock only that Room
    exclusively while keeping its parent resources shared.

    Physical bed inventory remains the responsibility of BedService
    and AccommodationMigrationService.
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
        Lock and retrieve the current Building record.

        Room operations use a shared Building lock so that operations
        on different floors and rooms can proceed concurrently.

        BuildingService is responsible for operations that require
        an exclusive Building lock.
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
        Lock the Building first, followed by its Floor.

        The initial query only identifies the parent Building.
        The actual records are refreshed after their locks are acquired.

        This prevents an operation from proceeding with stale parent
        information while another service changes the hierarchy.
        """
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

        # Always acquire the parent lock before the Floor lock.
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

        # The Floor must still belong to the Building identified
        # before the locks were acquired.
        if locked_floor.building_id != building_id:
            raise ConflictError(
                "The floor's building changed during the operation. "
                "Please retry."
            )

        # Refresh the hierarchy and configuration relationships.
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
        Lock the Room's parent hierarchy and then the Room itself.

        Lock order:

            Building (shared)
                |
            Floor (shared)
                |
            Room (exclusive)

        Operations on different Rooms can proceed concurrently
        because they do not require exclusive locks on their
        common Building or Floor.
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

        # Verify that the Room still belongs to the locked Floor.
        if locked_room.floor_id != floor.pk:
            raise ConflictError(
                "The room's floor changed during the operation. "
                "Please retry."
            )

        # Refresh all configuration inheritance relationships.
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
        Retrieve the latest BedConfiguration under a shared lock.

        Accepts either a BedConfiguration instance or its primary key.

        Room operations only inspect configurations. Changes to
        configuration capacity are handled by BedConfigurationService.
        """
        configuration_id = getattr(
            configuration,
            "pk",
            configuration,
        )

        if configuration_id is None:
            raise ValidationError(
                "A valid bed configuration must be selected."
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
    # ROOM POSITION ALLOCATION
    # ---------------------------------------------------------

    @staticmethod
    def _next_room_position(floor):
        """
        Return the lowest available room position on the Floor.

        Existing positions are reused when gaps exist.

        The caller must hold an exclusive Floor lock before
        calculating the next position.

        When max_rooms_per_floor is NULL, positions are allocated
        without an upper limit.
        """
        occupied_positions = set(
            floor.rooms.values_list(
                "position",
                flat=True,
            )
        )

        position = 1

        while position in occupied_positions:
            position += 1

        maximum = floor.max_rooms_per_floor

        if maximum is not None and position > maximum:
            raise ConflictError(
                "This floor has reached its maximum room capacity."
            )

        return position

    # ---------------------------------------------------------
    # CONFIGURATION RESOLUTION
    # ---------------------------------------------------------

    @classmethod
    def _resolve_inherited_configuration(cls, floor):
        """
        Resolve the effective configuration without a Room override.

        Inheritance:

            Floor override -> Building default

        The selected configuration is retrieved under a shared lock
        so that its state cannot change during the operation.
        """
        configuration_id = (
            floor.bed_configuration_override_id
            or floor.building.default_bed_configuration_id
        )

        if configuration_id is None:
            raise ValidationError(
                "No effective bed configuration is assigned "
                "to this Floor or its Building."
            )

        return cls._get_configuration(configuration_id)

    @staticmethod
    def _validate_configuration(
        configuration,
    ):
        """
        Ensure that the selected configuration can be used.

        A configuration must exist, be active, and provide at least
        one permitted bed position.
        """
        if configuration is None:
            raise ValidationError(
                "A valid bed configuration must be assigned "
                "to the room."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The selected bed configuration is inactive."
            )

        if configuration.bed_count < 1:
            raise ValidationError(
                "The bed configuration must contain at least one bed."
            )

    @classmethod
    def _validate_configuration_capacity(
        cls,
        room,
        configuration,
    ):
        """
        Ensure the selected configuration accommodates existing beds.

        The highest existing physical bed position is checked rather
        than the number of Bed records.

        This includes beds in AVAILABLE, MAINTENANCE, OUT_OF_SERVICE,
        and RETIRED states.

        Retired records are preserved, so their positions cannot
        silently be made invalid by changing the configuration.

        An unsaved Room has no existing physical beds, so only
        configuration validity needs to be checked.

        The caller must hold an exclusive Room lock when validating
        an existing Room.
        """
        cls._validate_configuration(configuration)

        # During room creation, there cannot be any existing beds.
        if not room.pk:
            return
        
        beds = beds_requiring_valid_position(
            Bed.objects.filter(room_id=room.pk)
        )
        
        highest_position = beds.aggregate(
            highest_position=Max("position"),
        )["highest_position"]

        if (
            highest_position is not None
            and highest_position > configuration.bed_count
        ):
            raise ConflictError(
                "The selected configuration cannot accommodate "
                "the existing physical bed positions. "
                "Use the accommodation migration workflow to "
                "reduce the room's physical capacity safely."
            )

    # ---------------------------------------------------------
    # PERSISTENCE
    # ---------------------------------------------------------

    @staticmethod
    def _save_room(room):
        """
        Validate and persist a Room.

        The nested atomic block creates a savepoint. This allows
        database integrity errors to be translated into application
        exceptions without leaving the surrounding transaction unusable.
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
        Ensure that the Floor is operational before creating a Room.
        """

        if floor.status != Floor.FloorStatus.ACTIVE:
            raise ValidationError(
                "Rooms can only be created on active floors."
            )

    # ---------------------------------------------------------
    # ROOM CREATION
    # ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def create_room(
        cls,
        *,
        actor,
        floor,
        bed_configuration_override=None,
    ) -> Room:
        """
        Create a Room and automatically generate its physical beds.

        The Floor is exclusively locked before allocating a room
        position. This prevents concurrent requests from selecting
        the same position.

        When a Room-level configuration is not supplied, the Room
        inherits the Floor override or Building default.

        Room creation and physical bed generation share one outer
        transaction. If bed generation fails, the Room is rolled back.
        """
        floor_id = getattr(floor, "pk", floor)

        if floor_id is None:
            raise ValidationError(
                "A valid Floor must be supplied."
            )

        # Room positions are allocated per Floor.
        locked_floor = cls._get_locked_floor(
            floor_id,
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

        cls._validate_floor_for_room_creation(
            locked_floor
        )

        position = cls._next_room_position(
            locked_floor
        )

        room = Room(
            floor=locked_floor,
            position=position,
        )

        if bed_configuration_override is not None:
            configuration = cls._get_configuration(
                bed_configuration_override
            )

            room.bed_configuration_override = configuration

        else:
            configuration = (
                cls._resolve_inherited_configuration(
                    locked_floor
                )
            )

        cls._validate_configuration_capacity(
            room,
            configuration,
        )

        room = cls._save_room(room)

        # Keep the import local to avoid a circular dependency
        # between RoomService and BedService.
        from apps.accommodations.services.bed_service import (
            BedService,
        )

        # BedService generates missing physical bed records.
        # It preserves existing bed records and their statuses.
        # Any failure rolls back the Room creation as well.
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
    ) -> Room:
        """
        Update the Room's editable configuration.

        None means that no configuration change was requested.

        Removing a Room-level configuration override must use
        remove_bed_configuration_override().

        This method does not directly create, retire, or modify
        physical Bed records.
        """
        room_id = getattr(room, "pk", room)

        if room_id is None:
            raise ValidationError(
                "A valid Room must be supplied."
            )

        locked_room, _ = cls._get_locked_room(
            room_id
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
    ) -> Room:
        """
        Assign a Room-level bed configuration override.

        The selected configuration must be active and must accommodate
        every existing physical bed position.

        This operation changes the configuration inheritance reference.
        It does not retire, delete, or change the status of physical beds.

        Physical capacity reductions must go through the dedicated
        accommodation migration workflow.
        """
        room_id = getattr(room, "pk", room)

        if room_id is None:
            raise ValidationError(
                "A valid Room must be supplied."
            )

        locked_room, _ = cls._get_locked_room(
            room_id
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
    ) -> Room:
        """
        Remove the Room-level override and restore inherited configuration.

        Inheritance:

            Floor override -> Building default

        The inherited configuration must be active and must accommodate
        every existing physical bed position before the override is removed.

        No physical beds are deleted or automatically retired.
        """
        room_id = getattr(room, "pk", room)

        if room_id is None:
            raise ValidationError(
                "A valid Room must be supplied."
            )

        locked_room, _ = cls._get_locked_room(
            room_id
        )

        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to manage this room's operations."
            )

        if locked_room.bed_configuration_override_id is None:
            raise ValidationError(
                "This room does not have a configuration override."
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