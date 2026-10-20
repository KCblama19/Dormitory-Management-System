from django.db import transaction
from django.core.exceptions import ValidationError

# MODELS
from apps.university.models import University

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import PermissionDenied
class UniversityService:
    
    @staticmethod
    @transaction.atomic
    def create_university(
        *,
        actor,
        code: str,
        name: str,
        website:str ="",
        is_active=True,
    ) -> University | None:
        
        if not AccommodationPolicy.can_create_university(
            actor
        ):
            raise PermissionDenied(
                "Only administrators can create universities."
            )
        
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
    @transaction.atomic
    def activate_university(
        *, 
        actor,
        university: University
    ) -> University :
        
        if not AccommodationPolicy.can_activate_university(
            actor,
            university,
        ):
            raise PermissionDenied(
                "You do not have the permission to activate"
                "this university."
            )
            
        university.is_active = True,
        university.full_clean()
        university.save(update_fields=["is_active"])
        
        return university
    
    @staticmethod
    @transaction.atomic
    def deactivate_university(
        *, 
        actor,
        university: University
    ) -> University:
        
        if not AccommodationPolicy.can_deactivate_university(
            actor,
            university
        ):
            raise PermissionDenied(
                "You do not have he permission to "
                "deactivate this university."
            )
            
        university.is_active = False
        university.full_clean()
        university.save(update_fields=["is_active"])
        
        return university