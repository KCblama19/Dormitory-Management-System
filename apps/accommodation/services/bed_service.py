
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

# MODELS
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Room,
)
from apps.accommodation.models.floor.floor_model import Floor

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
    Handles physical bed creation, position changes, and operational status.

    Capacity is determined by the room's effective bed configuration.
    All operations lock the parent floor and room before modifying a bed,
    so concurrent operations follow a consistent accommodation hierarchy.
    """

    # ------------------------------------------------------------------
    # LOCKING
    # ------------------------------------------------------------------

    @staticmethod
    def _get_locked_room(room: Room):
        """
        Lock and refresh the room's parent floor and room.

        The lock order is Floor -> Room. The effective bed configuration
        is then retrieved and locked after the room, matching the order
        used by room- and floor-level configuration changes.
        """

        try:
            # Read the relationship identifier first. This query does not
            # acquire a lock, so it cannot invert the hierarchy's lock order.
            room_reference = Room.objects.values(
                "floor_id"
            ).get(pk=room.pk)

            floor = Floor.objects.select_for_update().get(
                pk=room_reference["floor_id"]
            )

            locked_room = Room.objects.select_for_update().get(
                pk=room.pk,
                floor_id=floor.pk,
            )

        except (Room.DoesNotExist, Floor.DoesNotExist) as exc:
            raise NotFoundError(
                "The requested room or its floor could not be found."
            ) from exc

        # Resolve the effective configuration from the freshly locked
        # room and floor records, rather than trusting the caller's object.
        if locked_room.bed_configuration_override_id:
            configuration_id = (
                locked_room.bed_configuration_override_id
            )
        elif floor.bed_configuration_override_id:
            configuration_id = floor.bed_configuration_override_id
        else:
            # The building's default is the final inheritance level.
            configuration_id = floor.building.default_bed_configuration_id

        configuration = None

        if configuration_id is not None:
            try:
                configuration = (
                    BedConfiguration.objects.select_for_update().get(
                        pk=configuration_id
                    )
                )
            except BedConfiguration.DoesNotExist as exc:
                raise NotFoundError(
                    "The room's effective bed configuration "
                    "could not be found."
                ) from exc

        return locked_room, floor, configuration

    @staticmethod
    def _get_locked_bed(bed: Bed):
        """
        Lock the parent floor, room, and finally the bed.

        Locking the parent room first coordinates bed operations with
        changes to the room's effective bed capacity.
        """

        try:
            bed_reference = Bed.objects.values(
                "room_id"
            ).get(pk=bed.pk)

            room_reference = Room.objects.values(
                "floor_id"
            ).get(pk=bed_reference["room_id"])

        except (Bed.DoesNotExist, Room.DoesNotExist) as exc:
            raise NotFoundError(
                "The requested bed or its room could not be found."
            ) from exc

        # Acquire the parent locks before locking the bed itself.
        room, floor, configuration = BedService._get_locked_room(
            Room(pk=bed_reference["room_id"])
        )

        try:
            locked_bed = Bed.objects.select_for_update().get(
                pk=bed.pk,
                room_id=room.pk,
            )
        except Bed.DoesNotExist as exc:
            raise NotFoundError(
                "The requested bed could not be found."
            ) from exc

        return locked_bed, room, floor, configuration

    # ------------------------------------------------------------------
    # VALIDATION AND PERSISTENCE
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_configuration(
        configuration: BedConfiguration | None,
    ) -> None:
        """Ensure the room has an active effective bed configuration."""

        if configuration is None:
            raise ValidationError(
                "The room has no effective bed configuration."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The room's effective bed configuration is inactive."
            )

    @staticmethod
    def _validate_position(position, configuration) -> None:
        """Validate a physical bed position against the effective capacity."""

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
    def _save_bed(bed: Bed) -> Bed:
        """
        Validate and persist a bed.

        The nested atomic block creates a savepoint. This ensures an
        IntegrityError is handled after the failed savepoint has rolled
        back, leaving the outer service transaction usable.
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
    def create_bed(
        *,
        actor,
        room,
        position,
    ) -> Bed:

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

        BedService._validate_position(
            position,
            configuration,
        )

        # A bed can only be created in an operational room.
        # Add further room/floor lifecycle rules here if those are
        # defined by your accommodation requirements.
        if not floor.is_active or floor.status != Floor.FloorStatus.ACTIVE:
            raise ValidationError(
                "Beds cannot be created on an inactive or "
                "non-active floor."
            )

        if Bed.objects.filter(
            room=locked_room,
            position=position,
        ).exists():
            raise ConflictError(
                f"Bed position {position} already exists "
                "in this room."
            )

        bed = Bed(
            room=locked_room,
            position=position,
            status=Bed.Status.AVAILABLE,
        )

        return BedService._save_bed(bed)

    # ------------------------------------------------------------------
    # BED POSITION
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def update_bed_position(
        *,
        actor,
        bed,
        position,
    ) -> Bed:

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

        BedService._validate_position(
            position,
            configuration,
        )

        # Exclude the current bed so an unchanged position is valid.
        duplicate_exists = (
            Bed.objects
            .filter(
                room=room,
                position=position,
            )
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
    def _change_status(
        *,
        actor,
        bed,
        new_status,
    ) -> Bed:
        """
        Shared authorization and persistence for bed status transitions.

        Individual public methods retain responsibility for validating
        which transitions are allowed.
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

        locked_bed.status = new_status

        return BedService._save_bed(locked_bed)

    @staticmethod
    @transaction.atomic
    def set_available(
        *,
        actor,
        bed,
    ) -> Bed:

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
    def set_maintenance(
        *,
        actor,
        bed,
    ) -> Bed:

        return BedService._change_status(
            actor=actor,
            bed=bed,
            new_status=Bed.Status.MAINTENANCE,
        )

    @staticmethod
    @transaction.atomic
    def set_out_of_service(
        *,
        actor,
        bed,
    ) -> Bed:

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

        # Occupancy validation belongs here once the Assignment
        # model and its lifecycle rules are implemented.
        locked_bed.status = Bed.Status.OUT_OF_SERVICE

        return BedService._save_bed(locked_bed)

    @staticmethod
    @transaction.atomic
    def restore_bed(
        *,
        actor,
        bed,
    ) -> Bed:

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