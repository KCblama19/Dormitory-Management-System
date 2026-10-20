from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.student.models.academic_year import AcademicYear

# POLICIES
from apps.core.policies import AcademicPolicy

# Application Exceptions
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    NotFoundError,
    PermissionDenied,
)


class AcademicYearService:

    @staticmethod
    @transaction.atomic
    def create(*, actor,
        name,
        start_date,
        end_date,
        is_active=True,
        is_current=False,
    ):
        if not AcademicPolicy.can_create_academic_year(actor):
            raise PermissionDenied(
                "You do not have permission to create academic years"
            )
            
        if not name or not name.strip():
            raise ValidationError("Academic year name is required.")

        if end_date <= start_date:
            raise ValidationError(
                "Academic year end date must be after start date."
            )

        if AcademicYear.objects.filter(name=name).exists():
            raise ConflictError(
                f"Academic year '{name}' already exists."
            )

        with transaction.atomic():

            if is_current:
                AcademicYear.objects.filter(
                    is_current=True
                ).update(is_current=False)

            academic_year = AcademicYear(
                name=name.strip(),
                start_date=start_date,
                end_date=end_date,
                is_active=is_active,
                is_current=is_current,
            )

            try:
                academic_year.full_clean()
                academic_year.save()
            except DjangoValidationError as exc:
                raise ValidationError(exc.message_dict)

            return academic_year

    @staticmethod
    def activate(*, actor, academic_year):
        if not AcademicPolicy.can_activate_academic_year(
            actor,
            academic_year,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this"
                "academic year"
            )
        academic_year.is_active = True
        academic_year.full_clean()
        academic_year.save(update_fields=["is_active"])
        
        return academic_year

    @staticmethod
    def deactivate(*, actor, academic_year):
        if not AcademicPolicy.can_deactivate_academic_year(
            actor, academic_year,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate"
                "this academic year."
            )
            
        if academic_year.is_current:
            raise ConflictError(
                "The current academic year cannot be deactivated."
            )

        academic_year.is_active = False
        academic_year.full_clean()
        academic_year.save(update_fields=["is_active"])

        return academic_year

    @staticmethod
    @transaction.atomic
    def set_current(*, actor, academic_year):
        
        if not AcademicPolicy.can_set_current_academic_year(
            actor, academic_year,
        ):
            raise PermissionDenied(
                "You do not have permission to change the "
                "the current academic year."
            )
            
        if not academic_year.is_active:
            raise ValidationError(
                "Only an active academic year can become current."
            )

        AcademicYear.objects.filter(
            is_current=True
        ).exclude(
            pk=academic_year.pk
        ).update(
            is_current=False
        )

        academic_year.is_current = True
        academic_year.full_clean()
        academic_year.save(update_fields=["is_current"])

        return academic_year