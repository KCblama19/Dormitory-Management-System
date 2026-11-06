
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
    NotFoundError,
)


class CampusService:
    """
    Handles campus creation, configuration updates, and operational
    state changes.

    Views and forms are responsible for collecting and validating
    user input. This service remains responsible for authorization,
    business rules, model validation, and persistence.
    """

    # =========================================================
    # PRIVATE HELPERS
    # =========================================================

    @staticmethod
    def _get_locked_campus(campus: Campus) -> Campus:
        """
        Retrieve the latest campus record and acquire a database lock.

        This prevents concurrent operations from modifying the same
        campus simultaneously on databases that support row locking.
        """
        try:
            return (
                Campus.objects
                .select_for_update()
                .select_related("university")
                .get(pk=campus.pk)
            )

        except Campus.DoesNotExist as exc:
            raise NotFoundError(
                "The requested campus could not be found."
            ) from exc

    @staticmethod
    def _normalize_text_fields(
        *,
        name: str,
        code: str,
        postal_code: str,
        address: str,
        city: str,
        province: str,
        description: str,
    ) -> dict:
        """
        Normalize text values independently of the forms.

        Services can be called from management commands, background
        processes, or other services, so normalization must not depend
        exclusively on form validation.
        """
        return {
            "name": name.strip(),
            "code": code.strip().upper(),
            "postal_code": postal_code.strip(),
            "address": address.strip(),
            "city": city.strip(),
            "province": province.strip(),
            "description": description.strip(),
        }

    @staticmethod
    def _save_campus(campus: Campus) -> Campus:
        """
        Run model validation and persist a campus.

        A nested atomic block provides a savepoint. This allows an
        IntegrityError to be translated without leaving the outer
        transaction in a broken state.
        """
        try:
            with transaction.atomic():
                campus.full_clean()
                campus.save()

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
                "The campus could not be saved because another "
                "campus already uses the specified name or code "
                "for this university."
            ) from exc

        return campus

    # =========================================================
    # CREATE
    # =========================================================

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
        """
        Create a campus under an existing university.

        New campuses are always created as active. Activation and
        deactivation are handled by their dedicated operations.
        """

        # --------------------------------------------------
        # 1. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_create_campus(actor):
            raise PermissionDenied(
                "Only administrators can create campuses."
            )

        # --------------------------------------------------
        # 2. Normalize user-provided values
        # --------------------------------------------------
        values = CampusService._normalize_text_fields(
            name=name,
            code=code,
            postal_code=postal_code,
            address=address,
            city=city,
            province=province,
            description=description,
        )

        # --------------------------------------------------
        # 3. Validate the parent university
        # --------------------------------------------------
        if not university.is_active:
            raise ValidationError(
                "Cannot create a campus under an inactive university."
            )

        # --------------------------------------------------
        # 4. Check campus name uniqueness
        # --------------------------------------------------
        if Campus.objects.for_university(university).filter(
            name=values["name"],
        ).exists():
            raise ValidationError(
                "A campus with this name already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 5. Check campus code uniqueness
        # --------------------------------------------------
        if Campus.objects.for_university(university).filter(
            code=values["code"],
        ).exists():
            raise ValidationError(
                "A campus with this code already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 6. Construct the campus
        # --------------------------------------------------
        campus = Campus(
            university=university,
            name=values["name"],
            code=values["code"],
            postal_code=values["postal_code"],
            address=values["address"],
            city=values["city"],
            province=values["province"],
            country=country,
            description=values["description"],
            is_active=True,
        )

        # --------------------------------------------------
        # 7. Validate and persist
        # --------------------------------------------------
        return CampusService._save_campus(campus)

    # =========================================================
    # UPDATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_campus(
        *,
        actor: Any,
        campus: Campus,
        name: str,
        code: str,
        postal_code: str = "",
        address: str = "",
        city: str = "",
        province: str = "",
        country=None,
        description: str = "",
    ) -> Campus:
        """
        Update an existing campus's descriptive and location fields.

        The university relationship is intentionally excluded.
        Changing a campus's parent university is not an ordinary
        campus configuration operation.
        """

        # --------------------------------------------------
        # 1. Retrieve and lock the current campus
        # --------------------------------------------------
        campus = CampusService._get_locked_campus(campus)

        # --------------------------------------------------
        # 2. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_update_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to update this campus."
            )

        # --------------------------------------------------
        # 3. Normalize user-provided values
        # --------------------------------------------------
        values = CampusService._normalize_text_fields(
            name=name,
            code=code,
            postal_code=postal_code,
            address=address,
            city=city,
            province=province,
            description=description,
        )

        # --------------------------------------------------
        # 4. Check campus name uniqueness
        # --------------------------------------------------
        duplicate_name = Campus.objects.for_university(
            campus.university,
        ).filter(
            name=values["name"],
        ).exclude(
            pk=campus.pk,
        ).exists()

        if duplicate_name:
            raise ValidationError(
                "A campus with this name already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 5. Check campus code uniqueness
        # --------------------------------------------------
        duplicate_code = Campus.objects.for_university(
            campus.university,
        ).filter(
            code=values["code"],
        ).exclude(
            pk=campus.pk,
        ).exists()

        if duplicate_code:
            raise ValidationError(
                "A campus with this code already exists "
                "for this university."
            )

        # --------------------------------------------------
        # 6. Apply the new values
        # --------------------------------------------------
        campus.name = values["name"]
        campus.code = values["code"]
        campus.postal_code = values["postal_code"]
        campus.address = values["address"]
        campus.city = values["city"]
        campus.province = values["province"]
        campus.country = country
        campus.description = values["description"]

        # --------------------------------------------------
        # 7. Validate and persist
        # --------------------------------------------------
        return CampusService._save_campus(campus)

    # =========================================================
    # ACTIVATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def activate_campus(
        *,
        actor: Any,
        campus: Campus,
    ) -> Campus:
        """
        Activate an existing campus.

        A campus cannot be activated while its parent university
        is inactive.
        """

        # --------------------------------------------------
        # 1. Retrieve and lock the current campus
        # --------------------------------------------------
        campus = CampusService._get_locked_campus(campus)

        # --------------------------------------------------
        # 2. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_activate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this campus."
            )

        # --------------------------------------------------
        # 3. Validate the parent university
        # --------------------------------------------------
        if not campus.university.is_active:
            raise ValidationError(
                "Cannot activate a campus under an inactive university."
            )

        # --------------------------------------------------
        # 4. Check current state
        # --------------------------------------------------
        if campus.is_active:
            raise ValidationError(
                "This campus is already active."
            )

        # --------------------------------------------------
        # 5. Activate and persist
        # --------------------------------------------------
        campus.is_active = True

        return CampusService._save_campus(campus)

    # =========================================================
    # DEACTIVATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def deactivate_campus(
        *,
        actor: Any,
        campus: Campus,
    ) -> Campus:
        """
        Deactivate a campus.

        A campus cannot be deactivated while it contains active
        buildings.
        """

        # --------------------------------------------------
        # 1. Retrieve and lock the current campus
        # --------------------------------------------------
        campus = CampusService._get_locked_campus(campus)

        # --------------------------------------------------
        # 2. Authorization
        # --------------------------------------------------
        if not AccommodationPolicy.can_deactivate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate this campus."
            )

        # --------------------------------------------------
        # 3. Check current state
        # --------------------------------------------------
        if not campus.is_active:
            raise ValidationError(
                "This campus is already inactive."
            )

        # --------------------------------------------------
        # 4. Validate dependent buildings
        # --------------------------------------------------
        if campus.buildings.active().exists():
            raise ValidationError(
                "Campus cannot be deactivated while it "
                "has active buildings."
            )

        # --------------------------------------------------
        # 5. Deactivate and persist
        # --------------------------------------------------
        campus.is_active = False

        return CampusService._save_campus(campus)