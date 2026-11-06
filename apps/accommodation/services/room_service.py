
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max

# Models
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Floor,
    Room,
)

# Policies
from apps.core.policies import AccommodationPolicy

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

    Room positions are allocated within a Floor.

    A Room's effective bed configuration follows this inheritance order:

        Room override → Floor override → Building default

    Physical Bed records remain the source of truth for existing capacity.
    """

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _next_room_position(floor):
        """
        Return the first available room position on the Floor.

        Positions are reused when gaps exist.

        Example:
            Existing positions: 1, 2, 4
            Next available position: 3

        The Floor must already be locked by the calling transaction.
        """

        occupied_positions = set(
            floor.rooms.values_list("position", flat=True)
        )

        for position in range(1, floor.max_rooms_per_floor + 1):
            if position not in occupied_positions:
                return position

        raise ConflictError(
            "This floor has reached its maximum room capacity."
        )

    @staticmethod
    def _get_locked_floor(floor_id):
        """
        Retrieve and lock the Floor before modifying its Rooms.

        Existing QuerySet methods handle eager loading of the Building
        and the Floor/Building bed-configuration relationships.
        """

        try:
            return (
                Floor.objects
                .select_for_update()
                .with_building()
                .with_configuration()
                .get(pk=floor_id)
            )

        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The requested floor could not be found."
            ) from exc

    @classmethod
    def _get_locked_room(cls, room_id):
        """
        Lock the parent Floor first, followed by the Room.

        This establishes a consistent lock order for room operations.
        """

        # Find the parent Floor before acquiring the row locks.
        try:
            floor_id = Room.objects.values_list(
                "floor_id",
                flat=True,
            ).get(pk=room_id)

        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The requested room could not be found."
            ) from exc

        floor = cls._get_locked_floor(floor_id)

        try:
            room = (
                Room.objects
                .select_for_update()
                .with_floor()
                .with_configuration()
                .get(pk=room_id)
            )

        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The requested room could not be found."
            ) from exc

        # The Room's parent Floor should not change during this operation.
        if room.floor_id != floor.pk:
            raise ConflictError(
                "The room's floor changed while the operation was being processed."
            )

        return room, floor

    @staticmethod
    def _get_configuration(configuration):
        """
        Retrieve and lock the latest BedConfiguration record.

        Locking the configuration prevents its active state or bed count
        from being changed concurrently while this operation validates it.
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
    def _validate_configuration_capacity(room, configuration):
        """
        Ensure a configuration accommodates every existing physical bed.

        The highest existing bed position is checked instead of counting
        Bed records because physical positions may contain gaps.

        Example:
            Existing positions: 1, 2, 4
            Existing bed count:  3

            A configuration with bed_count=3 is invalid because position 4
            exceeds the permitted configuration capacity.

        Maintenance and out-of-service beds are included because they
        still physically exist in the room.
        """

        if configuration is None:
            if Bed.objects.for_room(room).exists():
                raise ConflictError(
                    "The room has existing physical beds and cannot "
                    "use an empty bed configuration."
                )

            raise ValidationError(
                "A valid bed configuration must be assigned to the room."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The selected bed configuration is inactive."
            )

        highest_position = (
            Bed.objects
            .for_room(room)
            .aggregate(highest_position=Max("position"))
        )["highest_position"]

        if (
            highest_position is not None
            and highest_position > configuration.bed_count
        ):
            raise ConflictError(
                "The selected configuration cannot accommodate "
                "the existing physical bed positions."
            )

    @staticmethod
    def _save_room(room):
        """
        Validate and persist a Room.

        A nested atomic block creates a savepoint. This allows database
        integrity failures to be translated into application exceptions
        without leaving the surrounding transaction unusable.
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

    @classmethod
    @transaction.atomic
    def create_room(
        cls,
        *,
        actor,
        floor,
        bed_configuration_override=None,
    ):
        """
        Create a Room and allocate its position.

        The Floor is locked before calculating the next position.
        This coordinates concurrent room creation operations.

        When no room-level configuration is supplied, the Room inherits
        the Floor configuration or the Building default.
        """

        locked_floor = cls._get_locked_floor(floor.pk)

        if not AccommodationPolicy.can_create_room(
            actor,
            locked_floor,
        ):
            raise PermissionDenied(
                "You are not permitted to create rooms on this floor."
            )

        cls._validate_floor_for_room_creation(locked_floor)

        position = cls._next_room_position(locked_floor)

        room = Room(
            floor=locked_floor,
            position=position,
            bed_configuration_override=None,
        )

        if bed_configuration_override is not None:
            configuration = cls._get_configuration(
                bed_configuration_override
            )

            room.bed_configuration_override = configuration

        else:
            # Resolve the Floor override or Building default.
            configuration = cls._get_configuration(
                room.effective_bed_configuration
            )

        cls._validate_configuration_capacity(
            room,
            configuration,
        )

        cls._save_room(room)

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

        None means no configuration change. Use the dedicated
        remove_bed_configuration_override() method to remove an override.

        This method retains the existing room-update authorization rule.
        """

        locked_room, _ = cls._get_locked_room(room.pk)

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
        Assign a room-level bed configuration override.

        The selected configuration must be active and must accommodate
        all existing physical bed positions.
        """

        locked_room, _ = cls._get_locked_room(room.pk)

        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to manage this room's operations."
            )

        selected_configuration = cls._get_configuration(configuration)

        cls._validate_configuration_capacity(
            locked_room,
            selected_configuration,
        )

        locked_room.bed_configuration_override = selected_configuration

        cls._save_room(locked_room)

        return locked_room

    @classmethod
    @transaction.atomic
    def remove_bed_configuration_override(
        cls,
        *,
        actor,
        room,
    ):
        """
        Remove the room-level override and restore inherited configuration.

        The inherited configuration is resolved using:

            Floor override, if present
                ↓
            Building default

        The inherited configuration must accommodate the existing
        physical bed positions before the override can be removed.
        """

        locked_room, _ = cls._get_locked_room(room.pk)

        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You are not permitted to manage this room's operations."
            )

        inherited_configuration = cls._get_configuration(
            locked_room.floor.effective_bed_configuration
        )

        cls._validate_configuration_capacity(
            locked_room,
            inherited_configuration,
        )

        locked_room.bed_configuration_override = None

        cls._save_room(locked_room)

        return locked_room