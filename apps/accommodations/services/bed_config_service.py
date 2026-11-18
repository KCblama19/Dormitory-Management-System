from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q

from apps.assignments.services.commitment_queries import (
    beds_requiring_valid_position,
)

# MODELS
from apps.accommodations.models import (
    Bed,
    BedConfiguration,
)
from apps.accommodations.models.building.building_model import Building
from apps.accommodations.models.floor.floor_model import Floor
from apps.accommodations.models.room.room_model import Room

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


class BedConfigurationService:
    """
    Manages reusable bed configurations.

    A configuration can be inherited through three levels:

        Building default
            |
        Floor override
            |
        Room override

    Physical Bed records represent the beds that actually exist.
    The configuration determines the maximum permitted bed position.

    Locking protocol for configuration capacity and status changes:

        Building (exclusive, ascending primary-key order)
            |
        BedConfiguration (exclusive)

    Accommodation operations acquire shared locks on their parent
    buildings before reading or assigning a configuration. Therefore,
    an exclusive building lock coordinates configuration changes with
    operations on the affected accommodation hierarchy.
    """

    MINIMUM_BED_COUNT = 1

    # ------------------------------------------------------------------
    # LOCKING
    # ------------------------------------------------------------------

    @staticmethod
    def _get_locked_configuration(
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """Retrieve the latest configuration under an exclusive lock."""

        try:
            return get_locked_instance(
                BedConfiguration,
                configuration.pk,
                mode="exclusive",
            )
        except BedConfiguration.DoesNotExist as exc:
            raise NotFoundError(
                "The requested bed configuration could not be found."
            ) from exc

    @staticmethod
    def _lock_configuration_dependents(
        configuration: BedConfiguration,
    ) -> list[int]:
        """
        Exclusively lock buildings that currently reference this
        configuration.

        Building locks are acquired in ascending primary-key order to
        prevent concurrent configuration operations from acquiring
        multiple building locks in inconsistent orders.

        Child operations must acquire a shared building lock before
        accessing floors, rooms, or their effective configuration.
        """

        building_ids = list(
            Building.objects.filter(
                Q(
                    default_bed_configuration_id=configuration.pk
                )
                | Q(
                    floors__bed_configuration_override_id=configuration.pk
                )
                | Q(
                    floors__rooms__bed_configuration_override_id=configuration.pk
                )
            )
            .order_by("pk")
            .values_list("pk", flat=True)
            .distinct()
        )

        # Lock each building individually in deterministic order.
        # This avoids relying on database-specific behavior when
        # applying row locks to joined or distinct querysets.
        for building_id in building_ids:
            try:
                get_locked_instance(
                    Building,
                    building_id,
                    mode="exclusive",
                )
            except Building.DoesNotExist:
                raise ConflictError(
                    "An affected building changed while the bed "
                    "configuration was being updated. Please retry."
                )

        return building_ids

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_bed_count(bed_count) -> None:
        """Validate the type and minimum capacity requirements."""

        if (
            not isinstance(bed_count, int)
            or isinstance(bed_count, bool)
        ):
            raise ValidationError(
                "Bed count must be a valid whole number."
            )

        if bed_count < BedConfigurationService.MINIMUM_BED_COUNT:
            raise ValidationError(
                "A bed configuration must contain at least "
                f"{BedConfigurationService.MINIMUM_BED_COUNT} bed."
            )

    @staticmethod
    def _validate_name(name: str) -> str:
        """Normalize and validate the configuration name."""

        if not isinstance(name, str):
            raise ValidationError(
                "Bed configuration name must be text."
            )

        name = name.strip()

        if not name:
            raise ValidationError(
                "Bed configuration name is required."
            )

        return name

    @staticmethod
    def _validate_description(description: str) -> str:
        """Normalize an optional description."""

        if not isinstance(description, str):
            raise ValidationError(
                "Bed configuration description must be text."
            )

        return description.strip()

    @staticmethod
    def _validate_existing_bed_positions(
        configuration: BedConfiguration,
        new_bed_count: int,
    ) -> None:
        """
        Ensure that reducing capacity does not invalidate existing beds.

        A room inherits the configuration when:

        1. Its own override references the configuration; or
        2. It has no room override and its floor override references it; or
        3. Neither the room nor floor has an override and the building
           default references it.

        Every physical bed is considered, regardless of operational
        status. A bed in maintenance or out of service still occupies
        a physical position.
        """

        affected_rooms = Room.objects.filter(
            Q(
                bed_configuration_override_id=configuration.pk
            )
            | Q(
                bed_configuration_override__isnull=True,
                floor__bed_configuration_override_id=configuration.pk,
            )
            | Q(
                bed_configuration_override__isnull=True,
                floor__bed_configuration_override__isnull=True,
                floor__building__default_bed_configuration_id=configuration.pk,
            )
        )

        # Only the highest physical position in each room is needed.
        beds = beds_requiring_valid_position(
            Bed.objects.filter(
                room_id__in=affected_rooms.values("pk"),
            )
        )

        highest_positions = (
            beds.values("room_id")
            .annotate(highest_position=Max("position"))
            .filter(highest_position__gt=new_bed_count)
            .order_by("room_id")
        )

        invalid_room_ids = [
            item["room_id"]
            for item in highest_positions
        ]

        if invalid_room_ids:
            raise ConflictError(
                f"Cannot reduce this bed configuration to "
                f"{new_bed_count} beds. Existing physical bed "
                f"positions would exceed the proposed capacity "
                f"in rooms: {invalid_room_ids}."
            )

    @staticmethod
    def _validate_configuration_is_not_in_use(
        configuration: BedConfiguration,
    ) -> None:
        """
        Prevent deactivation while any building, floor, or room
        directly references this configuration.

        Inactive accommodation records are included because their
        configuration references still exist.
        """

        is_in_use = (
            Building.objects.filter(
                default_bed_configuration_id=configuration.pk
            ).exists()
            or Floor.objects.filter(
                bed_configuration_override_id=configuration.pk
            ).exists()
            or Room.objects.filter(
                bed_configuration_override_id=configuration.pk
            ).exists()
        )

        if is_in_use:
            raise ConflictError(
                "A bed configuration currently assigned to a "
                "building, floor, or room cannot be deactivated."
            )

    # ------------------------------------------------------------------
    # PERSISTENCE
    # ------------------------------------------------------------------

    @staticmethod
    def _save_configuration(
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """
        Validate and persist a configuration.

        The nested atomic block provides a savepoint. Database integrity
        errors are caught after that savepoint has rolled back, leaving
        the surrounding service transaction usable.
        """

        try:
            with transaction.atomic():
                configuration.full_clean()
                configuration.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The bed configuration could not be saved because "
                "it conflicts with an existing record."
            ) from exc

        return configuration

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_configuration(
        *,
        actor,
        name,
        bed_count,
        description="",
    ) -> BedConfiguration:
        """Create a new active bed configuration."""

        if not AccommodationPolicy.can_create_bed_configuration(
            actor,
        ):
            raise PermissionDenied(
                "You do not have permission to create "
                "bed configurations."
            )

        name = BedConfigurationService._validate_name(name)

        bed_count = bed_count
        BedConfigurationService._validate_bed_count(bed_count)

        description = (
            BedConfigurationService._validate_description(
                description
            )
        )

        if BedConfiguration.objects.filter(name=name).exists():
            raise ConflictError(
                f"Bed configuration '{name}' already exists."
            )

        configuration = BedConfiguration(
            name=name,
            bed_count=bed_count,
            description=description,
            is_active=True,
        )

        return BedConfigurationService._save_configuration(
            configuration
        )

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def update_configuration(
        *,
        actor,
        configuration,
        name=None,
        bed_count=None,
        description=None,
    ) -> BedConfiguration:
        """
        Update a configuration.

        Capacity changes lock all currently affected buildings before
        acquiring the configuration lock. Descriptive changes only
        require the configuration lock.
        """

        # A supplied capacity indicates that the caller intends to
        # modify capacity. Acquire dependent building locks first.
        if bed_count is not None:
            BedConfigurationService._lock_configuration_dependents(
                configuration
            )

        configuration = (
            BedConfigurationService._get_locked_configuration(
                configuration
            )
        )

        if not AccommodationPolicy.can_update_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to update "
                "this bed configuration."
            )

        if name is not None:
            configuration.name = (
                BedConfigurationService._validate_name(name)
            )

        if bed_count is not None:
            BedConfigurationService._validate_bed_count(
                bed_count
            )

            if bed_count != configuration.bed_count:
                BedConfigurationService._validate_existing_bed_positions(
                    configuration=configuration,
                    new_bed_count=bed_count,
                )

            configuration.bed_count = bed_count

        if description is not None:
            configuration.description = (
                BedConfigurationService._validate_description(
                    description
                )
            )

        return BedConfigurationService._save_configuration(
            configuration
        )

    # ------------------------------------------------------------------
    # ACTIVATE
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def activate_configuration(
        *,
        actor,
        configuration,
    ) -> BedConfiguration:
        """Activate an existing configuration."""

        configuration = (
            BedConfigurationService._get_locked_configuration(
                configuration
            )
        )

        if not AccommodationPolicy.can_activate_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to activate "
                "this bed configuration."
            )

        configuration.is_active = True

        return BedConfigurationService._save_configuration(
            configuration
        )

    # ------------------------------------------------------------------
    # DEACTIVATE
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def deactivate_configuration(
        *,
        actor,
        configuration,
    ) -> BedConfiguration:
        """
        Deactivate a configuration only when it is not referenced.

        Affected buildings are locked before the configuration so
        concurrent accommodation operations cannot assign or use the
        configuration while deactivation is being validated.
        """

        BedConfigurationService._lock_configuration_dependents(
            configuration
        )

        configuration = (
            BedConfigurationService._get_locked_configuration(
                configuration
            )
        )

        if not AccommodationPolicy.can_deactivate_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate "
                "this bed configuration."
            )

        BedConfigurationService._validate_configuration_is_not_in_use(
            configuration
        )

        configuration.is_active = False

        return BedConfigurationService._save_configuration(
            configuration
        )