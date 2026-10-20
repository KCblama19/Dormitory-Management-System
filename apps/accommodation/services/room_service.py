from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.accommodation.models import Room

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTION
from apps.core.exceptions import (
    ValidationError,
    PermissionDenied,
    ConflictError,
)


class RoomService:

    @staticmethod
    def _next_room_position(floor):
        existing_positions = set(
            floor.rooms.values_list(
                "position",
                flat=True,
            )
        )

        for position in range(
            1,
            floor.max_rooms_per_floor + 1,
        ):
            if position not in existing_positions:
                return position

        raise ConflictError(
            "This floor has reached its maximum number of rooms."
        )

    @staticmethod
    @transaction.atomic
    def create_room(
        *,
        actor,
        floor,
        bed_configuration_override=None,
    ):
        if not AccommodationPolicy.can_create_room(
            actor,
            floor,
        ):
            raise PermissionDenied(
                "You do not have permission to create room "
                "in this building."
            )
            
        if floor.status != "ACTIVE":
            raise ValidationError(
                "Rooms can only be created on active floors."
            )

        position = RoomService._next_room_position(
            floor
        )

        if (
            bed_configuration_override is not None
            and not bed_configuration_override.is_active
        ):
            raise ValidationError(
                "The bed configuration must be active."
            )

        room = Room(
            floor=floor,
            position=position,
            bed_configuration_override=bed_configuration_override,
        )

        try:
            room.full_clean()
            room.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return room

    @staticmethod
    @transaction.atomic
    def update_room(
        *,
        actor,
        room,
        bed_configuration_override=None,
    ):
        
        if not AccommodationPolicy.can_update_room(
            actor,
            room,
        ):
            raise PermissionDenied(
                "You do not have permission to update " 
                "room in this building."
            )

        if bed_configuration_override is not None:

            if not bed_configuration_override.is_active:
                raise ValidationError(
                    "The bed configuration must be active."
                )

            current_beds = room.beds.count()

            if (
                current_beds
                > bed_configuration_override.bed_count
            ):
                raise ConflictError(
                    "The selected configuration cannot contain "
                    "the room's existing physical beds."
                )

            room.bed_configuration_override = (
                bed_configuration_override
            )

        room.full_clean()
        room.save()

        return room

    @staticmethod
    @transaction.atomic
    def set_bed_configuration_override(
        *,
        actor,
        room,
        configuration,
    ):
        
        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            room,
        ):
            raise PermissionDenied(
                "You do not have permission to set bed "
                "configuration for this room."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The bed configuration must be active."
            )

        current_beds = room.beds.count()

        if current_beds > configuration.bed_count:
            raise ConflictError(
                "The configuration cannot contain the existing "
                "physical beds."
            )

        room.bed_configuration_override = configuration

        room.full_clean()
        room.save(
            update_fields=["bed_configuration_override"]
        )

        return room

    @staticmethod
    @transaction.atomic
    def remove_bed_configuration_override(*, actor, room):
        
        if not AccommodationPolicy.can_manage_room_operations(
            actor,
            room,
        ):
            raise PermissionDenied(
                "You do not have permission to update bed "
                "configuration for this room."
            )
        room.bed_configuration_override = None

        room.full_clean()
        room.save(
            update_fields=["bed_configuration_override"]
        )

        return room