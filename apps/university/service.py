from django.db import transaction
from django.core.exceptions import ValidationError

# MODELS
from apps.university.models import University

class UniversityService:
    
    @staticmethod
    @transaction.atomic
    def create_university(
        *,
        code: str,
        name: str,
        website:str ="",
        is_active=True,
    ) -> University | None:
        
        # Validate give data
        if not code:
            raise ValidationError(
                "University should have a code"
            )
            
        if not name:
            raise ValidationError(
                "University should have a name"
            )
            
        if University.objects.filter(
            name=name,
        ).exists():
            raise ValidationError(
                f"University '{name}' already exists"
            )
            
        university = University(
            code=code.strip(),
            name=name.strip(),
            website=website.strip(),
            is_active=is_active,
        )
        
        try:
            university.full_clean()
            university.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)
        
        return university
            
        
    @staticmethod
    def activate_university(*, university: University) -> University :
        university.is_active = True,
        university.full_clean()
        university.save(update_fields=["is_active"])
        
        return university
        
    def deactivate_university(*, university: University) -> University:
        university.is_active = False
        university.full_clean()
        university.save(update_fields=["is_active"])
        
        return university