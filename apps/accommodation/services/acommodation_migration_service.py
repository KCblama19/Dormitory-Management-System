from django.db import transaction

from apps.core.exceptions import (
    ValidationError,
    ConflictError,
)

from apps.accommodation.models import Bed


class AccommodationMigrationService:

    REDUCE = "REDUCE"
    EXPAND = "EXPAND"
    RECONFIGURE = "RECONFIGURE"

    @staticmethod
    def inspect_room_configuration(
        *,
        room,
        new_configuration,
    ):

        current_configuration = (
            room.effective_bed_configuration
        )

        current_count = room.beds.count()
        target_count = new_configuration.bed_count

        return {
            "room": room,
            "current_configuration": current_configuration,
            "new_configuration": new_configuration,
            "current_physical_bed_count": current_count,
            "target_bed_count": target_count,
            "requires_reduction": (
                target_count < current_count
            ),
            "requires_expansion": (
                target_count > current_count
            ),
            "excess_beds": list(
                room.beds
                .filter(position__gt=target_count)
                .order_by("position")
            ),
        }

    @staticmethod
    @transaction.atomic
    def expand_room(
        *,
        room,
        new_configuration,
    ):

        if not new_configuration.is_active:
            raise ValidationError(
                "The new configuration must be active."
            )

        current_count = room.beds.count()
        target_count = new_configuration.bed_count

        if target_count <= current_count:
            raise ValidationError(
                "Expansion requires the target configuration "
                "to have more beds than currently exist."
            )

        room.bed_configuration_override = (
            new_configuration
        )

        room.full_clean()
        room.save(
            update_fields=["bed_configuration_override"]
        )

        created_beds = []

        for position in range(
            current_count + 1,
            target_count + 1,
        ):
            bed = Bed(
                room=room,
                position=position,
                status=Bed.Status.AVAILABLE,
            )

            bed.full_clean()
            bed.save()

            created_beds.append(bed)

        return {
            "room": room,
            "created_beds": created_beds,
        }

    @staticmethod
    def prepare_reduction(
        *,
        room,
        new_configuration,
    ):

        current_count = room.beds.count()
        target_count = new_configuration.bed_count

        if target_count >= current_count:
            raise ValidationError(
                "This operation is not a reduction."
            )

        excess_beds = (
            room.beds
            .filter(position__gt=target_count)
            .order_by("position")
        )

        occupied_excess = [
            bed
            for bed in excess_beds
            if bed.is_occupied
        ]

        if occupied_excess:
            raise ConflictError(
                "One or more physical beds that would be "
                "removed are occupied. Assignment migration "
                "must be completed first."
            )

        return {
            "room": room,
            "target_configuration": new_configuration,
            "beds_requiring_removal": list(excess_beds),
        }

    @staticmethod
    @transaction.atomic
    def apply_reduction(
        *,
        room,
        new_configuration,
        beds_to_remove,
    ):

        target_count = new_configuration.bed_count

        expected_beds = set(
            room.beds
            .filter(position__gt=target_count)
            .values_list("pk", flat=True)
        )

        requested_beds = {
            bed.pk
            for bed in beds_to_remove
        }

        if expected_beds != requested_beds:
            raise ValidationError(
                "The supplied beds do not exactly match the "
                "physical beds that exceed the new configuration."
            )

        for bed in beds_to_remove:

            if bed.is_occupied:
                raise ConflictError(
                    f"Bed {bed.code} is occupied and cannot "
                    "be removed."
                )

        # IMPORTANT:
        # We intentionally do not delete the beds.
        # Physical removal is represented by moving them
        # out of service until a formal physical-removal
        # process exists.

        for bed in beds_to_remove:
            bed.status = Bed.Status.OUT_OF_SERVICE
            bed.full_clean()
            bed.save(update_fields=["status"])

        room.bed_configuration_override = new_configuration

        room.full_clean()
        room.save(
            update_fields=["bed_configuration_override"]
        )

        return {
            "room": room,
            "removed_from_service": beds_to_remove,
        }

    @staticmethod
    @transaction.atomic
    def reconfigure_room(
        *,
        room,
        new_configuration,
        beds_to_remove=None,
    ):

        if not new_configuration.is_active:
            raise ValidationError(
                "The new configuration must be active."
            )

        current_count = room.beds.count()
        target_count = new_configuration.bed_count

        if target_count == current_count:

            room.bed_configuration_override = (
                new_configuration
            )

            room.full_clean()
            room.save(
                update_fields=["bed_configuration_override"]
            )

            return {
                "room": room,
                "created_beds": [],
                "removed_from_service": [],
            }

        if target_count > current_count:
            return AccommodationMigrationService.expand_room(
                room=room,
                new_configuration=new_configuration,
            )

        if beds_to_remove is None:
            raise ValidationError(
                "Reducing a room's physical capacity requires "
                "an explicit list of beds to remove from service."
            )

        return AccommodationMigrationService.apply_reduction(
            room=room,
            new_configuration=new_configuration,
            beds_to_remove=beds_to_remove,
        )