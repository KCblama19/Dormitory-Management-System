from django.db import transaction

# MODELS
from apps.accommodation.models.floor.floor_model import Floor

# Exceptions
from django.core.exceptions import ValidationError
class FloorService:
    
    @staticmethod
    def _next_floor_number(building):
        
        existing_numbers = set(
            building.floors.values_list(
                "floor_number",
                flat=True,
            )
        )
        
        for floor_number in range(
            1,
            building.max_floors + 1,
        ):
            if floor_number not in existing_numbers:
                return floor_number
            
        raise ValidationError(
            "The building has reached its maximum number" 
            "of floors"
        )
    
    @staticmethod
    @transaction.atomic
    def create_floor(
        *,
        building,
        max_floors_per_room,
        gender_configuration=None,
        bed_configuration_override=None,
        restriction_note=None,
        is_restricted=False
    ):
        building = (
            type(building).objects
            .select_for_updates()
            .get(pk=building.pk)
        )
        
        if not building.is_active:
            raise ValidationError(
                "Cannot create a floor in an inactive building"
            )
            
        floor_number = FloorService._next_floor_number(
            building
        )
        
        if gender_configuration is not None:
            if building.gender_policy != "MIXED":
                raise ValidationError(
                    "Floor-level gender configuration is"
                    "only allowed in a mixed-gender building."
                )
                
        if bed_configuration_override is not None:
            if not bed_configuration_override.is_active:
                raise ValidationError(
                    "An inactive bed configuration cannot"
                    "be used"
                )
                
        floor = Floor(
            building=building,
            floor_number=floor_number,
            max_floors_per_room=max_floors_per_room,
            gender_configuration=gender_configuration,
            bed_configuration_override=bed_configuration_override,
            restriction_note=restriction_note,
            is_restricted=is_restricted,
        )
        
        try:
            floor.full_clean()
            floor.save()
        except:
            raise ValidationError(
                "Floor creation failed"
            )
            
        return Floor
    
    @staticmethod
    @transaction.atomic
    def update_floor(floor, **changes):
        
        allowed_fields = {
            "max_rooms_per_floor",
            "gender_configuration",
            "restriction_note",
            "is_restricted",
        }
        
        for field in allowed_fields:
            if field not in allowed_fields:
                raise ValidationError(
                    f"'{field}' cannot be edited"
                )
                
        if "max_rooms_per_floor" in changes:
            new_limit = changes["max_rooms_per_floor"]
            current_rooms = floor.rooms.count()
            
            if new_limit < current_rooms:
                raise ValidationError(
                    "Maximum rooms cannot be lower than the"
                    "number of existing rooms"
                )
                
        if "gender_configuration" in changes:
            gender = changes["gender_configuration"]
            
            if (
                gender is not None
                and floor.building.gender_policy != "MIXED"
            ):
                raise ValidationError(
                    "Floor gender configuration is only"
                    "allowed in a mixed-gender building."
                )
                
        for field, value in changes.items():
            setattr(floor, field, value)
            
        floor.full_clean()
        floor.save()

        return floor

    @staticmethod
    @transaction.atomic
    def activate_floor(floor):

        if not floor.building.is_active:
            raise ValidationError(
                "Cannot activate a floor inside an inactive building."
            )

        floor.status = Floor.FloorStatus.ACTIVE
        floor.save(update_fields=["status"])

        return floor

    @staticmethod
    @transaction.atomic
    def deactivate_floor(floor):

        if floor.rooms.filter(
            beds__status="AVAILABLE"
        ).exists():
            raise ConflictError(
                "Cannot deactivate a floor containing available beds."
            )

        floor.status = Floor.FloorStatus.INACTIVE
        floor.save(update_fields=["status"])

        return floor

    @staticmethod
    @transaction.atomic
    def set_maintenance(floor):

        floor.status = Floor.FloorStatus.MAINTENANCE
        floor.save(update_fields=["status"])

        return floor

    @staticmethod
    @transaction.atomic
    def set_restriction(
        floor,
        note=None,
    ):

        if not note:
            raise ValidationError(
                "A restriction note is required."
            )

        floor.is_restricted = True
        floor.restriction_note = note

        floor.save(
            update_fields=[
                "is_restricted",
                "restriction_note",
            ]
        )

        return floor

    @staticmethod
    @transaction.atomic
    def remove_restriction(floor):

        floor.is_restricted = False
        floor.restriction_note = None

        floor.save(
            update_fields=[
                "is_restricted",
                "restriction_note",
            ]
        )

        return floor

    @staticmethod
    @transaction.atomic
    def set_bed_configuration_override(
        floor,
        configuration,
    ):

        if not configuration.is_active:
            raise ValidationError(
                "An inactive configuration cannot be used."
            )

        floor.bed_configuration_override = configuration

        floor.full_clean()
        floor.save(
            update_fields=[
                "bed_configuration_override"
            ]
        )

        return floor

    @staticmethod
    @transaction.atomic
    def remove_bed_configuration_override(floor):

        floor.bed_configuration_override = None

        floor.save(
            update_fields=[
                "bed_configuration_override"
            ]
        )

        return floor