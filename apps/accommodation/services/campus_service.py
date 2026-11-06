
from typing import Any

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.accommodation.models.campus.campus_model import Campus

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    PermissionDenied,
    ValidationError,
    ConflictError,
)


class CampusService:

    @staticmethod
    @transaction.atomic
    def create_campus(
        *,
        actor: Any,
        university,
        name: str,
        code: str,
        postal_code: str = "",
        address: str = "",
        city: str = "",
        province: str = "",
        country=None,
        description: str = "",
    ) -> Campus:

        # --------------------------------------------------
        # 1. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_create_campus(
            actor,
        ):
            raise PermissionDenied(
                "Only administrators can create campuses."
            )

        # --------------------------------------------------
        # 2. Normalize user-provided values
        # --------------------------------------------------
        # The service must enforce normalization independently
        # of the form because it may also be called directly.
        name = name.strip()
        code = code.strip().upper()

        postal_code = postal_code.strip()
        address = address.strip()
        city = city.strip()
        province = province.strip()
        description = description.strip()

        # --------------------------------------------------
        # 3. Validate the parent university
        # --------------------------------------------------
        if not university.is_active:
            raise ValidationError(
                "Cannot create a campus under an "
                "inactive university."
            )

        # --------------------------------------------------
        # 4. Validate campus name uniqueness
        # --------------------------------------------------
        # Reject creation when another campus under the same
        # university already uses this normalized name.
        if Campus.objects.for_university(
            university,
        ).filter(
            name=name,
        ).exists():
            raise ValidationError(
                "A campus with this name already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 5. Validate campus code uniqueness
        # --------------------------------------------------
        # Codes are normalized to uppercase before checking.
        # This ensures service calls follow the same convention
        # as CampusForm.clean_code().
        if Campus.objects.for_university(
            university,
        ).filter(
            code=code,
        ).exists():
            raise ValidationError(
                "A campus with this code already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 6. Construct the campus instance
        # --------------------------------------------------
        campus = Campus(
            university=university,
            name=name,
            code=code,
            postal_code=postal_code,
            address=address,
            city=city,
            province=province,
            country=country,
            description=description,
            is_active=True,
        )

        # --------------------------------------------------
        # 7. Validate and persist
        # --------------------------------------------------
        # full_clean() validates model fields and constraints.
        # The database constraints remain the final protection
        # against concurrent duplicate creation.
        try:
            with transaction.atomic():
                campus.full_clean()
                campus.save()
                
        except DjangoValidationError as exc:
            # Convert Django's model validation errors into a domain error.
            messages = "; ".join(
                f"{field}: {', '.join(errors)}"
                for field, errors in exc.message_dict.items()
            ) if hasattr(exc, "message_dict") else "; ".join(exc.messages)

            raise ValidationError(messages) from exc

        except IntegrityError as exc:
            raise ConflictError(
                "A campus with the specified name or code already exists "
                "for this university."
            ) from exc

        return campus

    @staticmethod
    @transaction.atomic
    def activate_campus(
        *,
        actor: Any,
        campus: Campus,
    ) -> Campus:

        # --------------------------------------------------
        # 1. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_activate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to "
                "activate this campus."
            )

        # --------------------------------------------------
        # 2. Validate the parent university
        # --------------------------------------------------
        if not campus.university.is_active:
            raise ValidationError(
                "Cannot activate a campus under an "
                "inactive university."
            )

        # --------------------------------------------------
        # 3. Activate the campus
        # --------------------------------------------------
        campus.is_active = True

        # --------------------------------------------------
        # 4. Validate and persist
        # --------------------------------------------------
        try:
            campus.full_clean()
            campus.save(
                update_fields=["is_active"]
            )

        except DjangoValidationError as exc:
            raise ValidationError(
                exc.message_dict
            ) from exc

        return campus

    @staticmethod
    @transaction.atomic
    def deactivate_campus(
        *,
        actor: Any,
        campus: Campus,
    ) -> Campus:

        # --------------------------------------------------
        # 1. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_deactivate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to "
                "deactivate this campus."
            )

        # --------------------------------------------------
        # 2. Validate dependent buildings
        # --------------------------------------------------
        # A campus cannot be deactivated while it contains
        # active buildings.
        if campus.buildings.active().exists():
            raise ValidationError(
                "Campus cannot be deactivated while it "
                "has active buildings."
            )

        # --------------------------------------------------
        # 3. Deactivate the campus
        # --------------------------------------------------
        campus.is_active = False

        # --------------------------------------------------
        # 4. Validate and persist
        # --------------------------------------------------
        try:
            campus.full_clean()
            campus.save(
                update_fields=["is_active"]
            )

        except DjangoValidationError as exc:
            raise ValidationError(
                exc.message_dict
            ) from exc

        return campus