from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

# MODELS
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Room,
)
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.floor.floor_model import Floor

# DATABASE LOCKING
from apps.core.db.locking import get_locked_instance

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)


class BedService:
    """
    Manages physical beds within accommodation rooms.

    A room's effective bed configuration determines its physical capacity.
    Bed positions are allocated automatically, starting with the lowest
    unused positive position.

    Locking protocol:
        Building (shared)
        -> Floor (shared)
        -> Room (exclusive)
        -> BedConfiguration (shared)
        -> Bed (exclusive, when modifying an existing bed)

    The room-level exclusive lock serializes bed operations within the
    same room while allowing operations on different rooms to proceed
    concurrently.
    """

    # ------------------------------------------------------------------
    # LOCKING
    # ------------------------------------------------------------------

    @staticmethod
    def _get_locked_room(room: Room):
        """
        Lock and refresh the room's hierarchy and effective configuration.

        The initial relationship lookups are deliberately unlocked. They
        only identify the parent rows needed to acquire locks in the
        correct hierarchy order.
        """

        try:
            room_reference = Room.objects.values("floor_id").get(
                pk=room.pk
            )

            floor_reference = Floor.objects.values(
                "building_id"
            ).get(pk=room_reference["floor_id"])

        except (Room.DoesNotExist, Floor.DoesNotExist) as exc:
            raise NotFoundError(
                "The requested room or its floor could not be found."
            ) from exc

        # Ancestors must be locked before their descendants.
        BedService._get_locked_building(
            floor_reference["building_id"]
        )

        floor = BedService._get_locked_floor(
            room_reference["floor_id"]
        )

        try:
            locked_room = get_locked_instance(
                Room,
                room.pk,
                mode="exclusive",
            )
        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The requested room could not be found."
            ) from exc

        # The room's parent relationship must not have changed while
        # the hierarchy locks were being acquired.
        if locked_room.floor_id != floor.pk:
            raise ConflictError(
                "The room's floor changed during the operation. "
                "Please retry."
            )

        # Refresh the room with the current inheritance hierarchy.
        locked_room = (
            Room.objects
            .select_related(
                "floor",
                "floor__building",
            )
            .get(pk=locked_room.pk)
        )

        # Resolve the effective configuration:
        # Room override -> Floor override -> Building default.
        if locked_room.bed_configuration_override_id:
            configuration_id = (
                locked_room.bed_configuration_override_id
            )
        elif floor.bed_configuration_override_id:
            configuration_id = (
                floor.bed_configuration_override_id
            )
        else:
            configuration_id = (
                floor.building.default_bed_configuration_id
            )

        configuration = None

        if configuration_id is not None:
            try:
                configuration = get_locked_instance(
                    BedConfiguration,
                    configuration_id,
                    mode="shared",
                )
            except BedConfiguration.DoesNotExist as exc:
                raise NotFoundError(
                    "The room's effective bed configuration "
                    "could not be found."
                ) from exc

        return locked_room, floor, configuration

    @staticmethod
    def _get_locked_building(building_id):
        """Acquire a shared lock on the room's parent building."""

        try:
            return get_locked_instance(
                Building,
                building_id,
                mode="shared",
            )
        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The room's building could not be found."
            ) from exc

    @staticmethod
    def _get_locked_floor(floor_id):
        """Acquire a shared lock on the room's parent floor."""

        try:
            return get_locked_instance(
                Floor,
                floor_id,
                mode="shared",
            )
        except Floor.DoesNotExist as exc:
            raise NotFoundError(
                "The room's floor could not be found."
            ) from exc

    @staticmethod
    def _get_locked_bed(bed: Bed):
        """
        Lock the bed's parent hierarchy before locking the bed itself.
        """

        try:
            bed_reference = Bed.objects.values("room_id").get(
                pk=bed.pk
            )
        except Bed.DoesNotExist as exc:
            raise NotFoundError(
                "The requested bed could not be found."
            ) from exc

        room, floor, configuration = BedService._get_locked_room(
            Room(pk=bed_reference["room_id"])
        )

        try:
            locked_bed = get_locked_instance(
                Bed,
                bed.pk,
                mode="exclusive",
            )
        except Bed.DoesNotExist as exc:
            raise NotFoundError(
                "The requested bed could not be found."
            ) from exc

        if locked_bed.room_id != room.pk:
            raise ConflictError(
                "The bed's room changed during the operation. "
                "Please retry."
            )

        return locked_bed, room, floor, configuration

    # ------------------------------------------------------------------
    # CONFIGURATION AND CAPACITY
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_configuration(
        configuration: BedConfiguration | None,
    ) -> None:
        """Require an active effective bed configuration."""

        if configuration is None:
            raise ValidationError(
                "The room has no effective bed configuration."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The room's effective bed configuration is inactive."
            )

    @staticmethod
    def _validate_floor_operational(floor: Floor) -> None:
        """Prevent bed creation on floors that cannot accept operations."""

        if (
            not floor.is_active
            or floor.status != Floor.FloorStatus.ACTIVE
        ):
            raise ConflictError(
                "Beds cannot be created on an inactive or "
                "non-active floor."
            )

    @staticmethod
    def _validate_position(position: int, configuration) -> None:
        """Validate a position against the configured bed capacity."""

        if (
            not isinstance(position, int)
            or isinstance(position, bool)
        ):
            raise ValidationError(
                "Bed position must be a valid whole number."
            )

        if position < 1:
            raise ValidationError(
                "Bed position must be at least 1."
            )

        if position > configuration.bed_count:
            raise ValidationError(
                "Bed position exceeds the room's configured "
                "bed capacity."
            )

    @staticmethod
    def _next_bed_position(room: Room, configuration) -> int:
        """
        Return the lowest unused position within the room's capacity.

        The caller must already hold the room's exclusive lock. This
        prevents concurrent service operations from allocating the same
        position in that room.
        """

        BedService._validate_configuration(configuration)

        existing_positions = set(
            Bed.objects.filter(room=room).values_list(
                "position",
                flat=True,
            )
        )

        for position in range(1, configuration.bed_count + 1):
            if position not in existing_positions:
                return position

        raise ConflictError(
            "This room has reached its configured bed capacity."
        )

    # ------------------------------------------------------------------
    # PERSISTENCE
    # ------------------------------------------------------------------

    @staticmethod
    def _save_bed(bed: Bed) -> Bed:
        """
        Validate and persist a bed.

        A nested transaction creates a savepoint so that a database
        constraint failure does not leave the caller's outer transaction
        unusable.
        """

        try:
            with transaction.atomic():
                bed.full_clean()
                bed.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The bed could not be saved because its position "
                "conflicts with an existing record."
            ) from exc

        return bed

    # ------------------------------------------------------------------
    # BED CREATION
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_bed(*, actor, room) -> Bed:
        """
        Create one bed at the lowest unused position.

        Position allocation and persistence happen while the room's
        exclusive lock is held.
        """

        locked_room, floor, configuration = (
            BedService._get_locked_room(room)
        )

        if not AccommodationPolicy.can_create_bed(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You do not have permission to create beds "
                "in this room."
            )

        BedService._validate_configuration(configuration)
        BedService._validate_floor_operational(floor)

        position = BedService._next_bed_position(
            locked_room,
            configuration,
        )

        bed = Bed(
            room=locked_room,
            position=position,
            status=Bed.Status.AVAILABLE,
        )

        return BedService._save_bed(bed)

    @staticmethod
    @transaction.atomic
    def generate_beds(*, actor, room) -> list[Bed]:
        """
        Generate all missing physical beds for a room.

        This operation is idempotent:
        - Existing beds are preserved.
        - Existing bed statuses are not changed.
        - Only missing positions are created.
        - Existing positions beyond the configured capacity cause
          the operation to fail rather than silently deleting records.

        The method is intended to be called by RoomService during room
        creation, but can also be used to fill missing beds later.
        """

        locked_room, floor, configuration = (
            BedService._get_locked_room(room)
        )

        if not AccommodationPolicy.can_create_bed(
            actor,
            locked_room,
        ):
            raise PermissionDenied(
                "You do not have permission to generate beds "
                "in this room."
            )

        BedService._validate_configuration(configuration)
        BedService._validate_floor_operational(floor)

        existing_positions = set(
            Bed.objects.filter(room=locked_room).values_list(
                "position",
                flat=True,
            )
        )

        # Never remove or silently invalidate existing physical beds.
        if (
            existing_positions
            and max(existing_positions) > configuration.bed_count
        ):
            raise ConflictError(
                "The room contains bed positions beyond its "
                "configured capacity. Resolve the existing beds "
                "before generating additional beds."
            )

        created_beds = []

        for position in range(1, configuration.bed_count + 1):
            if position in existing_positions:
                continue

            bed = Bed(
                room=locked_room,
                position=position,
                status=Bed.Status.AVAILABLE,
            )

            created_beds.append(
                BedService._save_bed(bed)
            )

        return created_beds

    # ------------------------------------------------------------------
    # BED POSITION
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def update_bed_position(*, actor, bed, position) -> Bed:
        """Change a bed's physical position within its current room."""

        locked_bed, room, floor, configuration = (
            BedService._get_locked_bed(bed)
        )

        if not AccommodationPolicy.can_change_bed_position(
            actor,
            locked_bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "bed's physical position."
            )

        BedService._validate_configuration(configuration)
        BedService._validate_position(position, configuration)

        duplicate_exists = (
            Bed.objects
            .filter(room=room, position=position)
            .exclude(pk=locked_bed.pk)
            .exists()
        )

        if duplicate_exists:
            raise ConflictError(
                f"Bed position {position} already exists "
                "in this room."
            )

        locked_bed.position = position

        return BedService._save_bed(locked_bed)

    # ------------------------------------------------------------------
    # BED STATUS
    # ------------------------------------------------------------------

    @staticmethod
    def _change_status(*, actor, bed, new_status) -> Bed:
        """Authorize and persist a bed status transition."""

        locked_bed, room, floor, configuration = (
            BedService._get_locked_bed(bed)
        )

        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            locked_bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this bed's status."
            )

        locked_bed.status = new_status

        return BedService._save_bed(locked_bed)

    @staticmethod
    @transaction.atomic
    def set_available(*, actor, bed) -> Bed:
        """Make a bed available unless it is out of service."""

        locked_bed, room, floor, configuration = (
            BedService._get_locked_bed(bed)
        )

        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            locked_bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this bed's status."
            )

        if locked_bed.status == Bed.Status.OUT_OF_SERVICE:
            raise ValidationError(
                "An out-of-service bed must be restored before "
                "it can become available."
            )

        locked_bed.status = Bed.Status.AVAILABLE

        return BedService._save_bed(locked_bed)

    @staticmethod
    @transaction.atomic
    def set_maintenance(*, actor, bed) -> Bed:
        """Place a bed into maintenance."""

        return BedService._change_status(
            actor=actor,
            bed=bed,
            new_status=Bed.Status.MAINTENANCE,
        )

    @staticmethod
    @transaction.atomic
    def set_out_of_service(*, actor, bed) -> Bed:
        """
        Take a bed out of service.

        An active-assignment check must be added when the Assignment
        model and its lifecycle rules are available.
        """

        locked_bed, room, floor, configuration = (
            BedService._get_locked_bed(bed)
        )

        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            locked_bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this bed's status."
            )

        locked_bed.status = Bed.Status.OUT_OF_SERVICE

        return BedService._save_bed(locked_bed)

    @staticmethod
    @transaction.atomic
    def restore_bed(*, actor, bed) -> Bed:
        """Restore an out-of-service bed to available status."""

        locked_bed, room, floor, configuration = (
            BedService._get_locked_bed(bed)
        )

        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            locked_bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this bed's status."
            )

        if locked_bed.status != Bed.Status.OUT_OF_SERVICE:
            raise ValidationError(
                "Only out-of-service beds can be restored."
            )

        locked_bed.status = Bed.Status.AVAILABLE

        return BedService._save_bed(locked_bed)