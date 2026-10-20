from django.db import transaction
from django.core.exceptions import ValidationError 

# MODELS
from apps.accommodation.models import Bed

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ValidationError,
    PermissionDenied,
)
class BedService:

    @staticmethod
    @transaction.atomic
    def create_bed(
        *,
        actor,
        room,
        position,
    ):
        if not AccommodationPolicy.can_create_bed(
            actor,
            room,
        ):
            raise PermissionError(
                "You do not have permission to create beds "
                "in this room."
            )
    
        configuration = room.effective_bed_configuration

        if configuration is None:
            raise ValidationError(
                "The room has no effective bed configuration."
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

        if Bed.objects.for_room(room).filter(
            position=position
        ).exists():
            raise ValidationError(
                f"Bed position {position} already exists "
                "in this room."
            )

        bed = Bed(
            room=room,
            position=position,
            status=Bed.Status.AVAILABLE,
        )

        try:
            bed.full_clean()
            bed.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)

        return bed

    @staticmethod
    @transaction.atomic
    def update_bed_position(
        *,
        actor,
        bed,
        position,
    ):
        if not AccommodationPolicy.can_change_bed_position(
            actor,
            bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "bed's physical position."
            )
            
        configuration = (
            bed.room.effective_bed_configuration
        )

        if configuration is None:
            raise ValidationError(
                "The room has no effective bed configuration."
            )

        if position < 1:
            raise ValidationError(
                "Bed position must be at least 1."
            )

        if position > configuration.bed_count:
            raise ValidationError(
                "Bed position exceeds the room's effective "
                "bed configuration."
            )

        if (
            Bed.objects
            .for_room(bed.room)
            .filter(position=position)
            .exclude(pk=bed.pk)
            .exists()
        ):
            raise ValidationError(
                f"Bed position {position} already exists."
            )

        bed.position = position

        bed.full_clean()
        bed.save(update_fields=["position"])

        return bed

    @staticmethod
    @transaction.atomic
    def set_available(*, actor, bed):
        
        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "bed's status."
            )
            
        if bed.status == Bed.Status.OUT_OF_SERVICE:
            raise ValidationError(
                "An out-of-service bed must be restored before "
                "it can become available."
            )

        bed.status = Bed.Status.AVAILABLE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed

    @staticmethod
    @transaction.atomic
    def set_maintenance(*, actor, bed):
        
        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            bed,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "bed's status."
            )
            
        bed.status = Bed.Status.MAINTENANCE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed

    @staticmethod
    @transaction.atomic
    def set_out_of_service(*, actor, bed):
        
        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            bed
        ):
            raise PermissionDenied(
                "You do not have permission to change "
                "this bed status."
            )
        if bed.is_occupied:
            raise ValidationError(
                "An occupied bed cannot be placed out of service."
            )

        bed.status = Bed.Status.OUT_OF_SERVICE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed

    @staticmethod
    @transaction.atomic
    def restore_bed(*, actor, bed):
        if not AccommodationPolicy.can_manage_bed_operations(
            actor,
            bed
        ):
            raise PermissionDenied(
                "You do not have permission to change "
                "this bed status."
            )
        
        if bed.status != Bed.Status.OUT_OF_SERVICE:
            raise ValidationError(
                "Only out-of-service beds can be restored."
            )

        bed.status = Bed.Status.AVAILABLE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed