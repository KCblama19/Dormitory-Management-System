from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from apps.core.db.locking import get_locked_instance


# MODELS
from apps.accommodation.models.campus.campus_model import Campus
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.models import (
    Bed,
    BedConfiguration,
    Room,
)

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)


class BuildingService:
    """
    Handles building creation, updates, and operational state changes.

    Building-level changes that affect dependent floors, rooms, or beds
    are validated before persistence. Database constraints remain the
    final protection against concurrent uniqueness violations.
    """

    # A single-gender building requires every active floor to use
    # the corresponding floor-level gender configuration.
    GENDER_MAPPING = {
        Building.GenderPolicy.MALE_ONLY:
            Floor.GenderConfiguration.MALE,

        Building.GenderPolicy.FEMALE_ONLY:
            Floor.GenderConfiguration.FEMALE,
    }

    # ------------------------------------------------------------------
    # LOCKING AND PERSISTENCE
    # ------------------------------------------------------------------
    
    @staticmethod
    def _get_locked_campus(campus: Campus) -> Campus:
        """
        Lock and refresh a campus before creating a building under it.

        Campus deactivation must use an exclusive Campus lock.
        Building creation uses a shared Campus lock so multiple
        buildings can be created concurrently on the same campus.
        """
        try:
            return get_locked_instance(
                Campus,
                campus.pk,
                mode="shared",
            )
        except Campus.DoesNotExist as exc:
            raise NotFoundError(
                "The requested campus could not be found."
            ) from exc
            
            
    @staticmethod
    def _get_locked_building(building: Building) -> Building:
        """
        Lock and refresh a building before performing a mutation.

        Building mutations require an exclusive lock because they can
        affect the operational state or configuration inherited by
        descendant floors, rooms, and beds.
        """
        try:
            return get_locked_instance(
                Building,
                building.pk,
                mode="exclusive",
            )
        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The requested building could not be found."
            ) from exc

    
    @staticmethod
    def _get_locked_configuration(
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """
        Acquire a shared lock on a configuration.

        Building operations that assign a configuration only need to
        read its current state. Configuration capacity changes will
        acquire exclusive locks through BedConfigurationService.
        """
        try:
            return get_locked_instance(
                BedConfiguration,
                configuration.pk,
                mode="shared",
            )
        except BedConfiguration.DoesNotExist as exc:
            raise NotFoundError(
                "The selected bed configuration could not be found."
            ) from exc

    @staticmethod
    def _save_building(building: Building) -> Building:
        """
        Validate and persist a building.

        The inner atomic block creates a savepoint. If a database
        constraint fails, the savepoint is rolled back before the
        IntegrityError is translated into an application exception.
        """

        try:
            with transaction.atomic():
                building.full_clean()
                building.save()

        except DjangoValidationError as exc:
            raise ValidationError(
                "; ".join(exc.messages)
            ) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The building could not be saved because it conflicts "
                "with an existing record."
            ) from exc

        return building

    # ------------------------------------------------------------------
    # VALIDATION HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_active_floor_gender(
        building: Building,
        gender_policy,
    ) -> None:
        """
        Ensure active floors comply with a proposed building policy.

        Mixed buildings permit either male or female floor configurations.
        Single-gender buildings require every active floor to match.
        """

        if gender_policy == Building.GenderPolicy.MIXED:
            return

        expected_gender = BuildingService.GENDER_MAPPING.get(
            gender_policy
        )

        if expected_gender is None:
            raise ValidationError(
                "Invalid building gender policy."
            )

        incompatible_floors = building.floors.filter(
            status=Floor.FloorStatus.ACTIVE
        ).exclude(
            gender_configuration=expected_gender
        )

        if incompatible_floors.exists():
            raise ValidationError(
                "The building contains active floors whose gender "
                "configuration conflicts with the proposed policy."
            )

    
    @staticmethod
    def _validate_default_configuration(
        building: Building,
        configuration: BedConfiguration,
    ) -> BedConfiguration:
        """
        Validate a proposed building default configuration.

        The caller must hold an exclusive lock on the building.

        Descendant operations coordinate through shared locks on their
        ancestor building. Therefore, while this building is exclusively
        locked, compliant child operations cannot modify its floors,
        rooms, or beds.

        Rooms with their own configuration override are excluded because
        they do not inherit the proposed building default.
        """

        # The configuration is only being inspected here. Its shared
        # lock prevents concurrent configuration updates from changing
        # its active state or capacity during validation.
        configuration = BuildingService._get_locked_configuration(
            configuration
        )

        if not configuration.is_active:
            raise ValidationError(
                "An inactive bed configuration cannot become "
                "the building default."
            )

        # Only rooms inheriting the building default are affected.
        # A room-level override takes precedence over this building
        # configuration and therefore remains unaffected.
        room_ids = list(
            Room.objects.filter(
                floor__building=building,
                floor__bed_configuration_override__isnull=True,
                bed_configuration_override__isnull=True,
            ).values_list(
                "pk",
                flat=True,
            )
        )

        if not room_ids:
            return configuration

        # Physical beds matter regardless of their operational status.
        # Checking the highest position catches gaps in numbering and
        # beds that are under maintenance or out of service.
        highest_positions = (
            Bed.objects
            .filter(room_id__in=room_ids)
            .values("room_id")
            .annotate(
                highest_position=Max("position"),
            )
        )

        incompatible_rooms = [
            item["room_id"]
            for item in highest_positions
            if item["highest_position"] > configuration.bed_count
        ]

        if incompatible_rooms:
            raise ConflictError(
                "The proposed default bed configuration cannot be "
                "applied because one or more rooms contain physical "
                "beds beyond its capacity. Update those rooms or "
                "their bed configurations first."
            )

        return configuration


    @staticmethod
    def _validate_max_floors(
        building: Building,
        max_floors,
    ) -> None:
        """
        Ensure the proposed floor limit does not exclude existing floors.

        The highest assigned floor number is used instead of the number
        of floor records, because floor numbering may contain gaps.
        """

        if max_floors < 1:
            raise ValidationError(
                "Maximum floors must be at least 1."
            )

        highest_floor_number = building.floors.aggregate(
            highest=Max("floor_number")
        )["highest"]

        if (
            highest_floor_number is not None
            and max_floors < highest_floor_number
        ):
            raise ValidationError(
                "Maximum floors cannot be reduced below "
                "the highest existing floor number."
            )

    # ------------------------------------------------------------------
    # INTERNAL CHANGE OPERATIONS
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_gender_policy(
        actor,
        building: Building,
        gender_policy,
    ) -> None:
        """Authorize and validate a building gender-policy change."""

        if not AccommodationPolicy.can_change_building_gender_policy(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "building's gender policy."
            )

        # Lock active floors before checking their current configuration.
        list(
            Floor.objects.select_for_update()
            .filter(
                building=building,
                status=Floor.FloorStatus.ACTIVE,
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )

        BuildingService._validate_active_floor_gender(
            building,
            gender_policy,
        )

        building.gender_policy = gender_policy

    @staticmethod
    def _apply_student_population(
        actor,
        building: Building,
        student_population,
    ) -> None:
        """Authorize and apply a student-population change."""

        if not AccommodationPolicy.can_change_building_population(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "building's student population."
            )

        building.student_population = student_population

    @staticmethod
    def _apply_default_bed_configuration(
        actor,
        building: Building,
        configuration: BedConfiguration,
    ) -> None:
        """Authorize and apply a validated building default configuration."""

        if not AccommodationPolicy.can_change_default_bed_configuration(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "building's default bed configuration."
            )

        configuration = BuildingService._validate_default_configuration(
            building,
            configuration,
        )

        building.default_bed_configuration = configuration

    # ------------------------------------------------------------------
    # BUILDING CREATION
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_building(
        *,
        actor,
        campus,
        building_number,
        name,
        code,
        student_population,
        gender_policy,
        max_floors,
        default_bed_configuration,
    ) -> Building:

        if not AccommodationPolicy.can_create_building(actor):
            raise PermissionDenied(
                "Only administrators can create buildings."
            )
        campus = BuildingService._get_locked_campus(campus)
        
        if not campus.is_active:
            raise ValidationError(
                "Cannot create a building on an inactive campus."
            )

        if max_floors < 1:
            raise ValidationError(
                "Maximum floors must be at least 1."
            )

        # Normalize values before performing duplicate checks.
        building_number = str(building_number).strip()
        name = name.strip()
        code = code.strip().upper()

        if not building_number or not name or not code:
            raise ValidationError(
                "Building number, name, and code are required."
            )

        if Building.objects.for_campus(campus).filter(
            building_number=building_number,
        ).exists():
            raise ConflictError(
                "A building with this number already exists "
                "on this campus."
            )

        if Building.objects.for_campus(campus).filter(
            code=code,
        ).exists():
            raise ConflictError(
                "A building with this code already exists "
                "on this campus."
            )

        # Refresh and lock the configuration so its active state is
        # checked against the current database record.
        default_bed_configuration = (
            BuildingService._get_locked_configuration(
                default_bed_configuration
            )
        )

        if not default_bed_configuration.is_active:
            raise ValidationError(
                "An inactive bed configuration cannot be used "
                "as the building default."
            )

        building = Building(
            campus=campus,
            building_number=building_number,
            name=name,
            code=code,
            student_population=student_population,
            gender_policy=gender_policy,
            max_floors=max_floors,
            default_bed_configuration=default_bed_configuration,
        )

        return BuildingService._save_building(building)

    # ------------------------------------------------------------------
    # BUILDING UPDATE
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def update_building(
        actor,
        building: Building,
        **changes,
    ) -> Building:

        # Refresh the object before authorization and validation.
        building = BuildingService._get_locked_building(building)

        if not AccommodationPolicy.can_update_building(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to update this building."
            )

        allowed_fields = {
            "building_number",
            "name",
            "code",
            "student_population",
            "gender_policy",
            "max_floors",
            "default_bed_configuration",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            field = sorted(unknown_fields)[0]
            raise ValidationError(
                f"'{field}' cannot be edited."
            )

        # Normalize ordinary text fields before validation.
        if "building_number" in changes:
            value = changes.pop("building_number")

            if value is not None:
                building.building_number = str(value).strip()

        if "name" in changes:
            value = changes.pop("name")

            if value is not None:
                building.name = value.strip()

        if "code" in changes:
            value = changes.pop("code")

            if value is not None:
                building.code = value.strip().upper()

        # Validate the floor limit only when the caller supplied it.
        if "max_floors" in changes:
            max_floors = changes.pop("max_floors")

            if max_floors is not None:
                BuildingService._validate_max_floors(
                    building,
                    max_floors,
                )
                building.max_floors = max_floors

        # Apply specialized changes through internal operations.
        # This avoids calling public atomic service methods from inside
        # another public service method and repeating authorization.
        if "gender_policy" in changes:
            gender_policy = changes.pop("gender_policy")

            if gender_policy is not None:
                BuildingService._apply_gender_policy(
                    actor,
                    building,
                    gender_policy,
                )

        if "student_population" in changes:
            student_population = changes.pop("student_population")

            if student_population is not None:
                BuildingService._apply_student_population(
                    actor,
                    building,
                    student_population,
                )

        if "default_bed_configuration" in changes:
            configuration = changes.pop("default_bed_configuration")

            if configuration is not None:
                BuildingService._apply_default_bed_configuration(
                    actor,
                    building,
                    configuration,
                )

        # All supported fields have been handled explicitly.
        # Persist the complete object once, after every business rule
        # has passed validation.
        return BuildingService._save_building(building)

    # ------------------------------------------------------------------
    # ACTIVATION AND DEACTIVATION
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def activate_building(
        actor,
        building: Building,
    ) -> Building:

        building = BuildingService._get_locked_building(building)

        if not AccommodationPolicy.can_activate_building(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this building."
            )

        if not building.campus.is_active:
            raise ValidationError(
                "Cannot activate a building on an inactive campus."
            )

        building.is_active = True

        return BuildingService._save_building(building)

    @staticmethod
    @transaction.atomic
    def deactivate_building(
        actor,
        building: Building,
    ) -> Building:

        building = BuildingService._get_locked_building(building)

        if not AccommodationPolicy.can_deactivate_building(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate this building."
            )

        # Lock floors before checking their operational state.
        active_floors = Floor.objects.select_for_update().filter(
            building=building,
            status=Floor.FloorStatus.ACTIVE,
        )

        if active_floors.exists():
            raise ValidationError(
                "Cannot deactivate a building while it contains "
                "active floors."
            )

        building.is_active = False

        return BuildingService._save_building(building)

    # ------------------------------------------------------------------
    # INDIVIDUAL CONFIGURATION CHANGES
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def change_gender_policy(
        actor,
        building: Building,
        gender_policy,
    ) -> Building:

        building = BuildingService._get_locked_building(building)

        BuildingService._apply_gender_policy(
            actor,
            building,
            gender_policy,
        )

        return BuildingService._save_building(building)

    @staticmethod
    @transaction.atomic
    def change_student_population(
        actor,
        building: Building,
        student_population,
    ) -> Building:

        building = BuildingService._get_locked_building(building)

        BuildingService._apply_student_population(
            actor,
            building,
            student_population,
        )

        return BuildingService._save_building(building)

    @staticmethod
    @transaction.atomic
    def change_default_bed_configuration(
        actor,
        building: Building,
        configuration: BedConfiguration,
    ) -> Building:

        building = BuildingService._get_locked_building(building)

        BuildingService._apply_default_bed_configuration(
            actor,
            building,
            configuration,
        )

        return BuildingService._save_building(building)
