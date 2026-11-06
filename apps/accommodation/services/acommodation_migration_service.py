
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Max

# MODELS
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Building,
    Floor,
    Room,
)

# POLICY
from dorm_system.apps.core.policies.accommodation_migration_policy import (
    AccommodationMigrationPolicy,
)

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    PermissionDenied,
    NotFoundError,
)


class AccommodationMigrationService:
    """
    Handles changes to a room's physical bed configuration.

    Migration types:
        - REDUCE: Retire physical beds exceeding the target capacity.
        - EXPAND: Create or restore physical beds to reach the target capacity.
        - RECONFIGURE: Change the room configuration without changing
          the final physical bed capacity.

    Retired beds are preserved in the database for historical purposes.
    They are excluded from the room's active physical capacity.

    Locking hierarchy:
        Building -> Floor -> Room -> BedConfiguration -> Bed

    All migration operations must follow this hierarchy to reduce
    the risk of concurrent accommodation changes.
    """

    REDUCE = "REDUCE"
    EXPAND = "EXPAND"
    RECONFIGURE = "RECONFIGURE"

    # ---------------------------------------------------------
    # LOCKING AND RETRIEVAL
    # ---------------------------------------------------------

    @staticmethod
    def _get_locked_room_context(room):
        """
        Lock the accommodation hierarchy associated with a room.

        The room's floor and building are retrieved first so that
        parent records can be locked before child records.

        Returns:
            tuple: (building, floor, room)
        """

        if not getattr(room, "pk", None):
            raise NotFoundError("The specified room does not exist.")

        # Retrieve the floor reference to identify the parent building.
        room_reference = Room.objects.filter(
            pk=room.pk
        ).values(
            "floor_id"
        ).first()

        if room_reference is None:
            raise NotFoundError("The specified room does not exist.")

        floor_reference = Floor.objects.filter(
            pk=room_reference["floor_id"]
        ).values(
            "building_id"
        ).first()

        if floor_reference is None:
            raise NotFoundError("The room's floor could not be found.")

        # Lock the hierarchy from parent to child.
        try:
            building = Building.objects.select_for_update().get(
                pk=floor_reference["building_id"]
            )

            floor = Floor.objects.select_for_update().get(
                pk=room_reference["floor_id"]
            )

            room = (
                Room.objects
                .select_for_update()
                .select_related(
                    "floor",
                    "floor__building",
                    "bed_configuration_override",
                    "floor__bed_configuration_override",
                    "floor__building__default_bed_configuration",
                )
                .get(pk=room.pk)
            )

        except (
            Building.DoesNotExist,
            Floor.DoesNotExist,
            Room.DoesNotExist,
        ) as exc:
            raise NotFoundError(
                "The accommodation hierarchy could not be found."
            ) from exc

        return building, floor, room

    @staticmethod
    def _get_locked_configuration(configuration):
        """
        Retrieve the latest configuration while holding a row lock.
        """

        if not configuration or not getattr(configuration, "pk", None):
            raise ValidationError(
                "A valid target bed configuration is required."
            )

        try:
            configuration = (
                BedConfiguration.objects
                .select_for_update()
                .get(pk=configuration.pk)
            )
        except BedConfiguration.DoesNotExist as exc:
            raise NotFoundError(
                "The selected bed configuration does not exist."
            ) from exc

        if not configuration.is_active:
            raise ValidationError(
                "The target bed configuration must be active."
            )

        return configuration

    @staticmethod
    def _get_locked_beds(room):
        """
        Lock every physical bed belonging to the room.

        Retired beds are included because their records may need
        to be restored during a future expansion.
        """

        return list(
            Bed.objects
            .select_for_update()
            .filter(room=room)
            .order_by("position", "pk")
        )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _check_permission(actor, room):
        """
        Centralize authorization for all migration operations.
        """

        if not AccommodationMigrationPolicy.can_migrate_room(
            actor,
            room,
        ):
            raise PermissionDenied(
                "You do not have permission to migrate this room."
            )

    @staticmethod
    def _validate_configuration(configuration):
        """
        Ensure that the target configuration can be assigned.
        """

        if configuration.bed_count < 1:
            raise ValidationError(
                "A bed configuration must contain at least one bed."
            )

        if not configuration.is_active:
            raise ValidationError(
                "The target bed configuration must be active."
            )

    @staticmethod
    def _get_active_beds(beds):
        """
        Return physical beds that have not been permanently retired.

        OUT_OF_SERVICE and MAINTENANCE beds still physically exist
        and therefore remain part of the room's capacity.
        """

        return [
            bed for bed in beds
            if bed.status != Bed.Status.RETIRED
        ]

    @staticmethod
    def _get_current_max_position(beds):
        """
        Return the highest position among non-retired physical beds.

        Counting records is insufficient because bed positions may
        contain gaps.
        """

        active_beds = (
            AccommodationMigrationService._get_active_beds(beds)
        )

        return max(
            (bed.position for bed in active_beds),
            default=0,
        )

    @staticmethod
    def _get_excess_beds(beds, target_count):
        """
        Identify non-retired beds whose positions exceed the target.
        """

        return [
            bed for bed in beds
            if (
                bed.status != Bed.Status.RETIRED
                and bed.position > target_count
            )
        ]

    @staticmethod
    def _validate_beds_are_unoccupied(beds):
        """
        Prevent retirement of beds that currently have active assignments.

        This depends on Bed.is_occupied being correctly implemented
        against the Assignment model.
        """

        occupied_beds = [
            bed for bed in beds
            if bed.is_occupied
        ]

        if occupied_beds:
            occupied_positions = ", ".join(
                str(bed.position)
                for bed in occupied_beds
            )

            raise ConflictError(
                "The following beds are occupied and cannot be retired: "
                f"{occupied_positions}. Complete the necessary assignment "
                "migration first."
            )

    @staticmethod
    def _save_instance(instance, conflict_message):
        """
        Validate and save a model instance inside a database savepoint.

        The nested atomic block allows an IntegrityError to be translated
        without leaving the surrounding migration transaction unusable.
        """

        try:
            with transaction.atomic():
                instance.full_clean()
                instance.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                conflict_message
            ) from exc

        return instance

    # ---------------------------------------------------------
    # INSPECTION
    # ---------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def inspect_room_configuration(
        *,
        actor,
        room,
        new_configuration,
    ):
        """
        Inspect the effects of assigning a new configuration.

        This is an informational operation. The result should not
        be treated as a guarantee that a later migration will succeed.
        """

        if not getattr(room, "pk", None):
            raise NotFoundError("The specified room does not exist.")

        try:
            room = (
                Room.objects
                .select_related(
                    "floor",
                    "floor__building",
                    "bed_configuration_override",
                    "floor__bed_configuration_override",
                    "floor__building__default_bed_configuration",
                )
                .get(pk=room.pk)
            )
        except Room.DoesNotExist as exc:
            raise NotFoundError(
                "The specified room does not exist."
            ) from exc

        AccommodationMigrationService._check_permission(
            actor,
            room,
        )

        configuration = (
            AccommodationMigrationService._get_locked_configuration(
                new_configuration
            )
        )

        current_configuration = room.effective_bed_configuration

        beds = list(
            Bed.objects.filter(room=room).order_by("position")
        )

        active_beds = (
            AccommodationMigrationService._get_active_beds(beds)
        )

        current_max_position = (
            AccommodationMigrationService._get_current_max_position(
                beds
            )
        )

        target_count = configuration.bed_count

        excess_beds = (
            AccommodationMigrationService._get_excess_beds(
                beds,
                target_count,
            )
        )

        return {
            "room": room,
            "current_configuration": current_configuration,
            "new_configuration": configuration,
            "current_physical_bed_count": len(active_beds),
            "current_max_position": current_max_position,
            "target_bed_count": target_count,
            "requires_reduction": bool(excess_beds),
            "requires_expansion": (
                target_count > current_max_position
            ),
            "excess_beds": excess_beds,
        }

    # ---------------------------------------------------------
    # EXPANSION
    # ---------------------------------------------------------

    @staticmethod
    def _expand_locked(room, configuration, beds):
        """
        Expand a room while its hierarchy and physical beds are locked.

        Existing retired beds are restored where possible. Missing
        positions are created as new physical bed records.

        Existing MAINTENANCE and OUT_OF_SERVICE beds are not silently
        changed back to AVAILABLE.
        """

        target_count = configuration.bed_count

        if target_count < 1:
            raise ValidationError(
                "The target configuration must contain at least one bed."
            )

        # Build a position lookup so that gaps and retired positions
        # can be handled without relying on the number of records.
        beds_by_position = {
            bed.position: bed
            for bed in beds
        }

        created_beds = []
        restored_beds = []

        for position in range(1, target_count + 1):
            existing_bed = beds_by_position.get(position)

            if existing_bed is None:
                bed = Bed(
                    room=room,
                    position=position,
                    status=Bed.Status.AVAILABLE,
                )

                AccommodationMigrationService._save_instance(
                    bed,
                    "A physical bed already exists at this position.",
                )

                created_beds.append(bed)
                continue

            if existing_bed.status == Bed.Status.RETIRED:
                # Restore the existing historical record instead of
                # creating another record with the same unique position.
                existing_bed.status = Bed.Status.AVAILABLE

                AccommodationMigrationService._save_instance(
                    existing_bed,
                    f"Could not restore bed at position {position}.",
                )

                restored_beds.append(existing_bed)

        room.bed_configuration_override = configuration

        AccommodationMigrationService._save_instance(
            room,
            "Could not update the room's bed configuration.",
        )

        return {
            "room": room,
            "created_beds": created_beds,
            "restored_beds": restored_beds,
            "removed_from_service": [],
        }

    @staticmethod
    @transaction.atomic
    def expand_room(
        *,
        actor,
        room,
        new_configuration,
    ):
        """
        Increase room capacity and create or restore physical beds.
        """

        building, floor, room = (
            AccommodationMigrationService._get_locked_room_context(
                room
            )
        )

        AccommodationMigrationService._check_permission(
            actor,
            room,
        )

        configuration = (
            AccommodationMigrationService._get_locked_configuration(
                new_configuration
            )
        )

        beds = (
            AccommodationMigrationService._get_locked_beds(room)
        )

        current_max_position = (
            AccommodationMigrationService._get_current_max_position(
                beds
            )
        )

        if configuration.bed_count <= current_max_position:
            raise ValidationError(
                "Expansion requires the target configuration to have "
                "a greater capacity than the current physical bed positions."
            )

        return AccommodationMigrationService._expand_locked(
            room,
            configuration,
            beds,
        )

    # ---------------------------------------------------------
    # REDUCTION PREPARATION
    # ---------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def prepare_reduction(
        *,
        actor,
        room,
        new_configuration,
    ):
        """
        Identify beds that must be retired before reducing capacity.

        This operation does not modify any physical bed or configuration.
        """

        building, floor, room = (
            AccommodationMigrationService._get_locked_room_context(
                room
            )
        )

        AccommodationMigrationService._check_permission(
            actor,
            room,
        )

        configuration = (
            AccommodationMigrationService._get_locked_configuration(
                new_configuration
            )
        )

        beds = (
            AccommodationMigrationService._get_locked_beds(room)
        )

        current_max_position = (
            AccommodationMigrationService._get_current_max_position(
                beds
            )
        )

        target_count = configuration.bed_count

        if target_count >= current_max_position:
            raise ValidationError(
                "This operation is not a reduction."
            )

        excess_beds = (
            AccommodationMigrationService._get_excess_beds(
                beds,
                target_count,
            )
        )

        AccommodationMigrationService._validate_beds_are_unoccupied(
            excess_beds
        )

        return {
            "room": room,
            "target_configuration": configuration,
            "current_max_position": current_max_position,
            "beds_requiring_removal": excess_beds,
        }

    # ---------------------------------------------------------
    # REDUCTION EXECUTION
    # ---------------------------------------------------------

    @staticmethod
    def _apply_reduction_locked(
        room,
        configuration,
        beds,
        beds_to_remove,
    ):
        """
        Retire excess physical beds and apply the new configuration.

        The caller must already hold the required hierarchy and bed locks.
        """

        target_count = configuration.bed_count

        expected_beds = (
            AccommodationMigrationService._get_excess_beds(
                beds,
                target_count,
            )
        )

        expected_ids = {
            bed.pk for bed in expected_beds
        }

        requested_ids = {
            bed.pk for bed in beds_to_remove
        }

        if expected_ids != requested_ids:
            raise ValidationError(
                "The supplied beds do not exactly match the physical "
                "beds that exceed the new configuration."
            )

        # Check occupancy again immediately before retirement.
        # Preparation results may have become stale.
        AccommodationMigrationService._validate_beds_are_unoccupied(
            expected_beds
        )

        # Retire the beds without deleting their records.
        for bed in expected_beds:
            bed.status = Bed.Status.RETIRED

            AccommodationMigrationService._save_instance(
                bed,
                f"Could not retire bed at position {bed.position}.",
            )

        # Once all excess beds are retired, the new configuration
        # can safely be assigned.
        room.bed_configuration_override = configuration

        AccommodationMigrationService._save_instance(
            room,
            "Could not update the room's bed configuration.",
        )

        return {
            "room": room,
            "removed_from_service": expected_beds,
        }

    @staticmethod
    @transaction.atomic
    def apply_reduction(
        *,
        actor,
        room,
        new_configuration,
        beds_to_remove,
    ):
        """
        Execute a prepared reduction.

        The supplied bed list is treated as a request, not trusted
        as authoritative. All affected beds are reidentified and
        revalidated under database locks.
        """

        building, floor, room = (
            AccommodationMigrationService._get_locked_room_context(
                room
            )
        )

        AccommodationMigrationService._check_permission(
            actor,
            room,
        )

        configuration = (
            AccommodationMigrationService._get_locked_configuration(
                new_configuration
            )
        )

        beds = (
            AccommodationMigrationService._get_locked_beds(room)
        )

        # Reject unsaved objects and objects without valid primary keys.
        requested_ids = set()

        for bed in beds_to_remove:
            if not getattr(bed, "pk", None):
                raise ValidationError(
                    "Every bed supplied for retirement must be a saved bed."
                )

            requested_ids.add(bed.pk)

        return AccommodationMigrationService._apply_reduction_locked(
            room=room,
            configuration=configuration,
            beds=beds,
            beds_to_remove=[
                bed for bed in beds
                if bed.pk in requested_ids
            ],
        )

    # ---------------------------------------------------------
    # GENERAL RECONFIGURATION
    # ---------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def reconfigure_room(
        *,
        actor,
        room,
        new_configuration,
        beds_to_remove=None,
    ):
        """
        Reconfigure a room through expansion, reduction, or
        equal-capacity configuration replacement.

        All decisions and writes occur under one transaction and
        one consistent set of hierarchy locks.
        """

        building, floor, room = (
            AccommodationMigrationService._get_locked_room_context(
                room
            )
        )

        AccommodationMigrationService._check_permission(
            actor,
            room,
        )

        configuration = (
            AccommodationMigrationService._get_locked_configuration(
                new_configuration
            )
        )

        beds = (
            AccommodationMigrationService._get_locked_beds(room)
        )

        current_max_position = (
            AccommodationMigrationService._get_current_max_position(
                beds
            )
        )

        target_count = configuration.bed_count

        # Expansion: create missing positions and restore retired ones.
        if target_count > current_max_position:
            return AccommodationMigrationService._expand_locked(
                room,
                configuration,
                beds,
            )

        # Reduction: explicitly identify and retire excess beds.
        if target_count < current_max_position:
            if beds_to_remove is None:
                raise ValidationError(
                    "Reducing a room's physical capacity requires "
                    "an explicit list of beds to retire."
                )

            requested_ids = set()

            for bed in beds_to_remove:
                if not getattr(bed, "pk", None):
                    raise ValidationError(
                        "Every bed supplied for retirement must be saved."
                    )

                requested_ids.add(bed.pk)

            return AccommodationMigrationService._apply_reduction_locked(
                room=room,
                configuration=configuration,
                beds=beds,
                beds_to_remove=[
                    bed for bed in beds
                    if bed.pk in requested_ids
                ],
            )

        # Equal capacity: only replace the configuration.
        # No physical bed records need to be created or retired.
        room.bed_configuration_override = configuration

        AccommodationMigrationService._save_instance(
            room,
            "Could not update the room's bed configuration.",
        )

        return {
            "room": room,
            "created_beds": [],
            "restored_beds": [],
            "removed_from_service": [],
        }