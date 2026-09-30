from django.db import transaction
from django.core.exceptions import ValidationError 

# MODELS
from apps.accommodation.models import Bed


class BedService:

    @staticmethod
    @transaction.atomic
    def create_bed(
        *,
        room,
        position,
    ):

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
                "Bed position exceeds the room's effective "
                "bed configuration."
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
        bed,
        position,
    ):

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
    def set_available(*, bed):

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
    def set_maintenance(*, bed):

        bed.status = Bed.Status.MAINTENANCE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed

    @staticmethod
    @transaction.atomic
    def set_out_of_service(*, bed):

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
    def restore_bed(*, bed):

        if bed.status != Bed.Status.OUT_OF_SERVICE:
            raise ValidationError(
                "Only out-of-service beds can be restored."
            )

        bed.status = Bed.Status.AVAILABLE

        bed.full_clean()
        bed.save(update_fields=["status"])

        return bed