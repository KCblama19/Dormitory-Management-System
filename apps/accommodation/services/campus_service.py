from django.db import transaction
from django.core.exceptions import ValidationError

# MODELS
from apps.accommodation.models.campus.campus_model import Campus

class CampusService:
    @staticmethod
    @transaction.atomic
    def create_campus(
        *,
        university,
        name: str,
        code: str,
        postal_code: str = "",
        address: str = "",
        city:str = "",
        province: str = "",
        country=None,
        description="",
    ) -> Campus:
        if not university.is_active:
            raise ValidationError(
                "Cannot create a campus under an " 
                "inactive university"
            )
            
        if not Campus.objects.for_university(
            university
        ).filter(
            name=name,
        ).exist():
            raise ValidationError(
                "A campus with this name already exists "
                "fot this university."
            )
            
        if not Campus.objects.for_university(
            university,
        ).filter(
            code=code,
        ).exist():
            raise ValidationError(
                "A campus with this code already exists "
                "for this university."
            )
            
        campus = Campus(
            university=university,
            name=name.strip(),
            code=code.strip(),
            postal_code=postal_code.strip(),
            address=address.strip(),
            city=city.strip(),
            province=province.strip(),
            country=country,
            description=description.strip(),
            is_active=True,
        )
        
        try:
            campus.full_clean()
            campus.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)
        
        return campus
    
    @staticmethod
    @transaction.atomic
    def activate_campus(*, campus: Campus) -> Campus:
        if not campus.university.is_active:
            raise ValidationError(
                "Cannot activate a campus under an "
                "inactive university."
            )
            
        campus.is_active = True
        campus.full_clean()
        campus.save(update_fields=["is_active"])
        
        return campus
    
    @staticmethod
    @transaction.atomic
    def deactivate_campus(*, campus: Campus) -> Campus:
        if campus.buildings.active().exists():
            raise ValidationError(
                "Campus cannot be deactivated while it "
                "has active buildings."
            )
            
        campus.is_active = False
        campus.full_clean()
        campus.save(update_fields=["is_active"])
        
        return campus