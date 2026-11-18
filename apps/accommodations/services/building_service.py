from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q

from apps.assignments.services.commitment_queries import (
    active_housing_assignments,
    building_has_unresolved_commitments,
    beds_requiring_valid_position,
)

# DATABASE LOCKING
from apps.core.db.locking import get_locked_instance

# MODELS
from apps.accommodations.models.campus.campus_model import Campus
from apps.accommodations.models.building.building_model import Building
from apps.accommodations.models.floor.floor_model import Floor
from apps.accommodations.models import (
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
    are validated before persistence.

    Lock order:
        Campus -> Building -> Floor -> Room -> BedConfiguration -> Bed

    Child operations must acquire a shared lock on their ancestor
    Building before acquiring locks on descendant resources.
    """

    GENDER_MAPPING = {
        Building.GenderPolicy.MALE_ONLY:
            Floor.GenderConfiguration.MALE,

        Building.GenderPolicy.FEMALE_ONLY:
            Floor.GenderConfiguration.FEMALE,
    }

    # =========================================================
    # LOCKING AND PERSISTENCE
    # =========================================================

    @staticmethod
    def _get_locked_campus(campus: Campus) -> Campus:
        """
        Acquire a shared Campus lock.

        Building creation and activation use this lock to coordinate
        with Campus deactivation, which requires an exclusive lock.
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
    def _get_building_campus_id(building: Building):
        """
        Read the current Campus ID before acquiring the hierarchy locks.

        The relationship is checked again after the Building is locked.
        Ordinary Building updates do not support changing campus_id.
        """
        try:
            return Building.objects.values_list(
                "campus_id",
                flat=True,
            ).get(pk=building.pk)
        except Building.DoesNotExist as exc:
            raise NotFoundError(
                "The requested building could not be found."
            ) from exc

    @staticmethod
    def _get_locked_building(building: Building) -> Building:
        """
        Acquire an exclusive Building lock and refresh the record.

        Callers must already hold any required ancestor locks.
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
        Acquire a shared configuration lock.

        Building operations only inspect or assign configurations.
        Capacity changes and deactivation are coordinated by
        BedConfigurationService using exclusive configuration locks.
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
        Validate and persist a Building.

        The nested atomic block creates a savepoint so database errors
        can be translated without breaking the surrounding transaction.
        """
        try:
            with transaction.atomic():
                building.full_clean()
                building.save()

        except DjangoValidationError as exc:
            messages = (
                "; ".join(
                    f"{field}: {', '.join(errors)}"
                    for field, errors in exc.message_dict.items()
                )
                if hasattr(exc, "message_dict")
                else "; ".join(exc.messages)
            )

            raise ValidationError(messages) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "The building could not be saved because it conflicts "
                "with an existing record."
            ) from exc

        return building

    # =========================================================
    # VALIDATION HELPERS
    # =========================================================

    @staticmethod
    def _validate_active_floor_gender(
        building: Building,
        gender_policy,
    ) -> None:
        """
        Ensure active floors comply with a proposed building policy.

        The caller must hold an exclusive Building lock. FloorService
        acquires a shared Building lock before modifying a Floor, so
        compliant Floor operations cannot race with this validation.
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
        Validate a proposed Building default configuration.

        The caller must hold an exclusive Building lock.

        Rooms with their own configuration override or a Floor-level
        override are excluded because they do not inherit this default.
        """
        configuration = BuildingService._get_locked_configuration(
            configuration
        )

        if not configuration.is_active:
            raise ValidationError(
                "An inactive bed configuration cannot become "
                "the building default."
            )

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

        beds = beds_requiring_valid_position(
            Bed.objects.filter(room_id__in=room_ids)
        )
        highest_positions = beds.values("room_id").annotate(
            highest_position=Max("position"),
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
        """Prevent reducing the floor limit below an existing floor number."""
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

    # =========================================================
    # INTERNAL CHANGE OPERATIONS
    # =========================================================

    @staticmethod
    def _apply_gender_policy(actor, building: Building, gender_policy) -> None:
        """Apply a building gender policy that permits existing commitments."""
        if not AccommodationPolicy.can_change_building_gender_policy(actor, building):
            raise PermissionDenied(
                "You do not have permission to change this building's gender policy."
            )

        if gender_policy == building.gender_policy:
            return

        BuildingService._validate_active_floor_gender(building, gender_policy)

        assignments = active_housing_assignments().filter(
            bed__room__floor__building_id=building.pk,
        )

        if gender_policy == Building.GenderPolicy.MIXED:
            # Moving to MIXED makes the stored floor gender settings
            # effective again, so check each assignment against its floor.
            incompatible = assignments.filter(
                (
                    Q(bed__room__floor__gender_configuration=Floor.GenderConfiguration.MALE)
                    & ~Q(student__gender__code="M")
                )
                | (
                    Q(bed__room__floor__gender_configuration=Floor.GenderConfiguration.FEMALE)
                    & ~Q(student__gender__code="F")
                )
            )
        else:
            required_gender = {
                Building.GenderPolicy.MALE_ONLY: "M",
                Building.GenderPolicy.FEMALE_ONLY: "F",
            }[gender_policy]
            incompatible = assignments.exclude(student__gender__code=required_gender)

        if incompatible.exists():
            raise ConflictError(
                "The proposed gender policy conflicts with a reservation "
                "or a checked-in student in this building."
            )

        building.gender_policy = gender_policy

    @staticmethod
    def _apply_student_population(
        actor,
        building: Building,
        student_population,
    ) -> None:
        """Apply a population policy that permits existing commitments."""
        if not AccommodationPolicy.can_change_building_population(actor, building):
            raise PermissionDenied(
                "You do not have permission to change this building's student population."
            )

        if student_population == building.student_population:
            return

        if student_population not in Building.StudentPopulation.values:
            raise ValidationError("Invalid building student population.")

        assignments = active_housing_assignments().filter(
            bed__room__floor__building_id=building.pk,
        )

        # Use the same nationality rule as allocation. Students without
        # a recorded nationality do not qualify for either population.
        if student_population == Building.StudentPopulation.CHINESE:
            incompatible = assignments.exclude(student__nationality="CN")
        else:
            incompatible = assignments.filter(
                Q(student__nationality__in=("CN", ""))
                | Q(student__nationality__isnull=True)
            )

        if incompatible.exists():
            raise ConflictError(
                "The proposed student population conflicts with a reservation "
                "or a checked-in student in this building."
            )

        building.student_population = student_population

    @staticmethod
    def _apply_default_bed_configuration(
        actor,
        building: Building,
        configuration: BedConfiguration,
    ) -> None:
        """Authorize and apply a validated Building default configuration."""
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

    # =========================================================
    # BUILDING CREATION
    # =========================================================

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

        # Shared Campus lock coordinates with Campus deactivation.
        campus = BuildingService._get_locked_campus(campus)

        if not campus.is_active:
            raise ValidationError(
                "Cannot create a building on an inactive campus."
            )

        if max_floors < 1:
            raise ValidationError(
                "Maximum floors must be at least 1."
            )

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

    # =========================================================
    # BUILDING UPDATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_building(
        actor,
        building: Building,
        **changes,
    ) -> Building:
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

        if "max_floors" in changes:
            max_floors = changes.pop("max_floors")

            if max_floors is not None:
                BuildingService._validate_max_floors(
                    building,
                    max_floors,
                )
                building.max_floors = max_floors

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

        return BuildingService._save_building(building)

    # =========================================================
    # ACTIVATION AND DEACTIVATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def activate_building(
        actor,
        building: Building,
    ) -> Building:
        """
        Activate a Building only when its Campus is active.

        Lock order: Campus shared -> Building exclusive.

        Campus deactivation acquires an exclusive Campus lock, so it
        cannot pass its active-Building check concurrently with this
        activation operation.
        """

        campus_id = BuildingService._get_building_campus_id(
            building
        )

        campus = BuildingService._get_locked_campus(
            Campus(pk=campus_id)
        )

        building = BuildingService._get_locked_building(building)

        if building.campus_id != campus.pk:
            raise ConflictError(
                "The building's campus changed while the operation "
                "was being prepared. Please retry."
            )

        if not AccommodationPolicy.can_activate_building(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this building."
            )

        if not campus.is_active:
            raise ValidationError(
                "Cannot activate a building on an inactive campus."
            )

        if building.is_active:
            raise ValidationError(
                "This building is already active."
            )

        building.is_active = True

        return BuildingService._save_building(building)

    @staticmethod
    @transaction.atomic
    def deactivate_building(actor, building: Building) -> Building:
        """Deactivate a building after its floors and commitments are resolved."""
        building = BuildingService._get_locked_building(building)

        if not AccommodationPolicy.can_deactivate_building(actor, building):
            raise PermissionDenied(
                "You do not have permission to deactivate this building."
            )

        if building.floors.filter(status=Floor.FloorStatus.ACTIVE).exists():
            raise ValidationError(
                "Cannot deactivate a building while it contains active floors."
            )

        if not building.is_active:
            raise ValidationError("This building is already inactive.")

        if building_has_unresolved_commitments(building_id=building.pk):
            raise ConflictError(
                "Resolve this building's reservations, assignments, "
                "allocation requests, and open transfers before deactivation."
            )

        building.is_active = False
        
        return BuildingService._save_building(building)

    # =========================================================
    # INDIVIDUAL CONFIGURATION CHANGES
    # =========================================================

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