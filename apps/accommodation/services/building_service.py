from django.db import transaction
from django.db.models import Count

# MODELS
from apps.accommodation.models.building.building_model import Building

from django.core.exceptions import ValidationError

class BuildingService:
    @staticmethod
    @transaction.atomic
    def create_building(
        *, campus,
        building_number, name,
        code, student_population,
        gender_policy, max_floors,
        default_bed_configuration,
    ):
        if not campus.is_active:
            raise ValidationError(
                "Cannot create a building on an inactive campus."
            )
        if max_floors < 1:
            raise ValidationError(
                "Maximum floor must be at least 1."
            )
            
        if not default_bed_configuration.is_active:
            raise ValidationError(
                "An inactive bed configuration cannot be" 
                "used as the building default."
            )
            
        if Building.objects.for_campus(campus).filter(
            building_number=building_number,
        ).exists():
            raise ValidationError(
                "A building with this number already exists"
                "on this campus."
            )
            
        if Building.objects.for_campus(campus).filter(
            code=code,
        ).exists():
            raise ValidationError(
                "A building with this code already exists"
                "on the campus."
            )
        
        building = Building(
            campus=campus,
            building_number=str(building_number).strip(),
            name=name.strip(),
            code=code.strip(),
            student_population=student_population,
            gender_policy=gender_policy,
            max_floors=max_floors,
            default_bed_configuration=default_bed_configuration,
        )
        
        try:
            building.full_clean()
            building.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)
        
        return building
    
    @ staticmethod
    @transaction.atomic
    def update_building(building, **changes):
        
        allowed_fields = {
            "building_number",
            "name",
            "code",
            "student_population",
            "gender_policy",
            "max_floors",
            "default_bed_configuration",
        }
        
        for field in changes:
            if field not in allowed_fields:
                raise ValidationError(
                    f"'{field}' cannot be edited"
                )
        
        if changes.get("name") is not None:
            name = changes.pop("name", None)
            building.name = name.strip()
            
        if changes.get("building_number") is not None:
            building_number = changes.pop("building_number", None)
            building.building_number = str(
                building_number
            ).strip()
            
        if changes.get("code") is not None:
            code = changes.pop("code", None)
            building.code = code.strip()
                
        if "max_floors" in changes:
            max_floors = changes["max_floors"]
            
            if max_floors < 1:
                raise ValidationError(
                    "Maximum floors must be at least 1."
                )
                
            current_floor_count = building.floors.count()
            
            if max_floors < current_floor_count:
                raise ValidationError(
                    "Maximum floors cannot be reduced"
                    "below the number of existing floors."
                )
                
            building.max_floors=max_floors
        
        gender_policy = changes.pop("gender_policy", None)
        student_population = changes.pop("student_population", None)
        default_bed_configuration = changes.pop("default_bed_configuration", None)
        
        if gender_policy is not None:
            BuildingService.change_gender_policy(building, gender_policy)
            
        if student_population is not None:
            BuildingService.change_student_population(building, student_population)
            
        if default_bed_configuration is not None:
            BuildingService.change_default_bed_configuration(
                building, default_bed_configuration)
                
        for field, value in changes.items():
            setattr(building, field, value)
        
        try:   
            building.full_clean()
            building.save(update_fields=[
                "building_number",
                "name",
                "code",
                "student_population",
                "gender_policy",
                "max_floors",
                "default_bed_configuration"
            ])
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)
        
        return building
        
    @staticmethod
    @transaction.atomic
    def activate_building(building):
        building.is_active = True
        building.save(update_fields=["is_active"])
        
    @staticmethod
    @transaction.atomic
    def deactivate_building(building):
        
        if building.floor.filter(
            status="ACTIVE"
        ).exists():
            raise ValidationError(
                "Cannot deactivate a building while it"
                "contains active floors"
            )
            
        building.is_active = False
        building.save(update_fields=["is_active"])
        
        return building
    
    @staticmethod
    @transaction.atomic
    def change_gender_policy(building, gender_policy):
        
        active_floors = building.floors.filter(
            status="ACTIVE"
        )
        
        if gender_policy != Building.GenderPolicy.MIXED:
            incompatible_floors = active_floors.exclude(
                gender_configuration=gender_policy.replace("_ONLY", "")
            )
            
            if incompatible_floors.exists():
                raise ValidationError(
                    "The building contains active floors"
                    "whose gender configuration conflicts"
                    "with the new building policy."
                )
                
        building.gender_policy = gender_policy
        building.full_clean()
        building.save(update_fields=["gender_policy"])
        
        return building
        
    @staticmethod
    @transaction.atomic
    def change_student_population(building, student_population):
        
        building.student_population = student_population
        building.full_clean()
        building.save(update_fields=["student_population"])
        
        return building
        
    @staticmethod
    @transaction.atomic
    def change_default_bed_configuration(
        building,
        configuration,
    ):
        if not configuration.is_active:
            raise ValidationError(
                "An inactive configuration cannot become"
                "the building default"
            )
            
        building.default_bed_configuration = configuration
        building.full_clean()
        building.save(update_fields=["default_bed_configuration"])
        
        return building
    