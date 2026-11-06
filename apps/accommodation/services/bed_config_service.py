
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q

# MODELS
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
)
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.models.room.room_model import Room

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
    Handles bed configuration creation, modification, and activation.

    A configuration can be inherited through three levels:

        Room override -> Floor override -> Building default

    Capacity changes must preserve the validity of every physical bed
    in every room whose effective configuration is being changed.
    """

    MINIMUM_BED_COUNT = 1

    # ------------------------------------------------------------------
    # LOCKING
    # ------------------------------------------------------------------

    @staticmethod
    def _get_locked_configuration(
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """Retrieve the latest configuration while acquiring a row lock."""

        try:
            return BedConfiguration.objects.select_for_update().get(
                pk=configuration.pk
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
        Lock the hierarchy containing rooms that may inherit this configuration.

        The lock order is:

            Building -> Floor -> Room -> BedConfiguration

        This is compatible with the hierarchy used by the accommodation
        services when changing inherited configurations or creating beds.

        Locking the dependent hierarchy before the configuration prevents
        capacity validation from racing with operations that follow the
        same parent-to-child locking convention.
        """

        # Find buildings that reference this configuration directly
        # or through one of their floors or rooms.
        building_ids = list(
            Building.objects.filter(
                Q(default_bed_configuration_id=configuration.pk)
                | Q(
                    floors__bed_configuration_override_id=configuration.pk
                )
                | Q(
                    floors__rooms__bed_configuration_override_id=configuration.pk
                )
            )
            .distinct()
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        if not building_ids:
            return []

        # Lock the affected buildings first.
        list(
            Building.objects.select_for_update()
            .filter(pk__in=building_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        # Lock every floor belonging to those buildings.
        floor_ids = list(
            Floor.objects.filter(
                building_id__in=building_ids
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        if not floor_ids:
            return []

        list(
            Floor.objects.select_for_update()
            .filter(pk__in=floor_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        # Lock the rooms under those floors. This also protects rooms
        # with their own overrides because they are part of the same
        # hierarchy, even though they will not inherit the changed
        # configuration.
        room_ids = list(
            Room.objects.filter(
                floor_id__in=floor_ids
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        if room_ids:
            list(
                Room.objects.select_for_update()
                .filter(pk__in=room_ids)
                .order_by("pk")
                .values_list("pk", flat=True)
            )

        return room_ids

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_bed_count(bed_count) -> None:
        """Validate the minimum and type requirements for configuration capacity."""

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
                f"{BedConfigurationService.MINIMUM_BED_COUNT} beds."
            )

    @staticmethod
    def _validate_existing_bed_positions(
        configuration: BedConfiguration,
        new_bed_count: int,
    ) -> None:
        """
        Ensure every room inheriting this configuration remains valid.

        A room inherits the configuration when:

        1. Its own override references this configuration; or
        2. It has no room override and its floor override references it; or
        3. Neither the room nor floor has an override and the building
           default references it.

        Physical bed positions are checked rather than bed counts.
        Beds in maintenance or out-of-service states are still physical
        beds and therefore remain relevant to capacity validation.
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

        # Only the highest position in each room matters for determining
        # whether the proposed capacity can contain all existing beds.
        highest_positions = (
            Bed.objects.filter(
                room_id__in=affected_rooms.values("pk")
            )
            .values("room_id")
            .annotate(
                highest_position=Max("position")
            )
        )

        invalid_room_ids = [
            item["room_id"]
            for item in highest_positions
            if item["highest_position"] > new_bed_count
        ]

        if invalid_room_ids:
            raise ConflictError(
                "Cannot reduce this bed configuration to "
                f"{new_bed_count} beds. Existing physical bed "
                "positions would exceed the proposed capacity "
                f"in rooms: {invalid_room_ids}."
            )

    # ------------------------------------------------------------------
    # PERSISTENCE
    # ------------------------------------------------------------------

    @staticmethod
    def _save_configuration(
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """
        Validate and save a configuration.

        The inner atomic block provides a savepoint so database integrity
        errors can be translated without leaving the outer transaction
        in a broken state.
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

        if not AccommodationPolicy.can_create_bed_configuration(
            actor,
        ):
            raise PermissionDenied(
                "You do not have permission to create "
                "bed configurations."
            )

        BedConfigurationService._validate_bed_count(bed_count)

        name = name.strip()
        description = description.strip()

        if not name:
            raise ValidationError(
                "Bed configuration name is required."
            )

        # This check provides a clear application-level error.
        # The database uniqueness constraint remains necessary because
        # another request could create the same name concurrently.
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

        # Capacity changes must lock dependent buildings, floors, and
        # rooms before locking the configuration itself.
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
            name = name.strip()

            if not name:
                raise ValidationError(
                    "Bed configuration name is required."
                )

            configuration.name = name

        if bed_count is not None:
            BedConfigurationService._validate_bed_count(
                bed_count
            )

            # Validate existing physical beds only when capacity changes.
            if bed_count != configuration.bed_count:
                BedConfigurationService._validate_existing_bed_positions(
                    configuration=configuration,
                    new_bed_count=bed_count,
                )

            configuration.bed_count = bed_count

        if description is not None:
            configuration.description = description.strip()

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

        # Lock the hierarchy before locking the configuration.
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

        # A configuration cannot be deactivated while referenced by
        # any building, floor, or room, even if the referencing record
        # is currently inactive.
        is_in_use = (
            Building.objects.filter(
                default_bed_configuration=configuration
            ).exists()
            or Floor.objects.filter(
                bed_configuration_override=configuration
            ).exists()
            or Room.objects.filter(
                bed_configuration_override=configuration
            ).exists()
        )

        if is_in_use:
            raise ConflictError(
                "A bed configuration currently assigned to a "
                "building, floor, or room cannot be deactivated."
            )

        configuration.is_active = False

        return BedConfigurationService._save_configuration(
            configuration
        )