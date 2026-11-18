from typing import Any

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.university.models import University
from apps.accommodations.models.campus.campus_model import Campus

# DATABASE LOCKING
from apps.core.db.locking import get_locked_instance

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

    Campus operations acquire a shared lock on their parent University
    before acquiring an exclusive lock on the Campus.
    """

    # =========================================================
    # PRIVATE HELPERS
    # =========================================================

    @staticmethod
    def _get_locked_university(university, mode="shared") -> University:
        """Retrieve and lock the current parent University."""
        try:
            return get_locked_instance(
                University,
                university.pk,
                mode=mode,
            )
        except University.DoesNotExist as exc:
            raise NotFoundError(
                "The requested university could not be found."
            ) from exc

    @staticmethod
    def _get_locked_campus(campus: Campus) -> Campus:
        """
        Lock the parent University before locking the Campus.

        The initial parent ID is read without a lock. The Campus is then
        locked, and its parent relationship is verified again.

        Ordinary Campus operations do not support changing university_id.
        """
        try:
            university_id = (
                Campus.objects
                .values_list("university_id", flat=True)
                .get(pk=campus.pk)
            )
        except Campus.DoesNotExist as exc:
            raise NotFoundError(
                "The requested campus could not be found."
            ) from exc

        # Parent first: University shared, then Campus exclusive.
        CampusService._get_locked_university(
            University(pk=university_id),
            mode="shared",
        )

        try:
            locked_campus = get_locked_instance(
                Campus,
                campus.pk,
                mode="exclusive",
            )
        except Campus.DoesNotExist as exc:
            raise NotFoundError(
                "The requested campus could not be found."
            ) from exc

        if locked_campus.university_id != university_id:
            raise ConflictError(
                "The campus's parent university changed while the "
                "operation was being prepared. Please retry."
            )

        return locked_campus

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
        """Normalize text values independently of form validation."""
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
        """Validate and persist a Campus using a savepoint."""
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
        university: University,
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
        Create a campus under an existing active University.

        New campuses are always created as active.
        """

        if not AccommodationPolicy.can_create_campus(actor):
            raise PermissionDenied(
                "Only administrators can create campuses."
            )

        values = CampusService._normalize_text_fields(
            name=name,
            code=code,
            postal_code=postal_code,
            address=address,
            city=city,
            province=province,
            description=description,
        )

        # A shared parent lock coordinates Campus creation with
        # University deactivation.
        university = CampusService._get_locked_university(
            university,
            mode="shared",
        )

        if not university.is_active:
            raise ValidationError(
                "Cannot create a campus under an inactive university."
            )

        if Campus.objects.for_university(university).filter(
            name=values["name"],
        ).exists():
            raise ValidationError(
                "A campus with this name already exists "
                "for this university."
            )

        if Campus.objects.for_university(university).filter(
            code=values["code"],
        ).exists():
            raise ValidationError(
                "A campus with this code already exists "
                "for this university."
            )

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
        Update descriptive and location fields.

        Changing the parent University is intentionally unsupported.
        """

        campus = CampusService._get_locked_campus(campus)

        if not AccommodationPolicy.can_update_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to update this campus."
            )

        values = CampusService._normalize_text_fields(
            name=name,
            code=code,
            postal_code=postal_code,
            address=address,
            city=city,
            province=province,
            description=description,
        )

        duplicate_name = Campus.objects.for_university(
            campus.university_id,
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

        duplicate_code = Campus.objects.for_university(
            campus.university_id,
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

        campus.name = values["name"]
        campus.code = values["code"]
        campus.postal_code = values["postal_code"]
        campus.address = values["address"]
        campus.city = values["city"]
        campus.province = values["province"]
        campus.country = country
        campus.description = values["description"]

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
        Activate a Campus only when its parent University is active.

        Lock order: University shared -> Campus exclusive.
        """

        campus = CampusService._get_locked_campus(campus)

        if not AccommodationPolicy.can_activate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this campus."
            )

        # The parent University is already shared-locked by
        # _get_locked_campus().
        if not campus.university.is_active:
            raise ValidationError(
                "Cannot activate a campus under an inactive university."
            )

        if campus.is_active:
            raise ValidationError(
                "This campus is already active."
            )

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
        Deactivate a Campus only when it has no active Buildings.

        Lock order: University shared -> Campus exclusive.

        Building creation and activation acquire a shared Campus lock,
        so they cannot race with this operation.
        """

        campus = CampusService._get_locked_campus(campus)

        if not AccommodationPolicy.can_deactivate_campus(
            actor,
            campus,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate this campus."
            )

        if not campus.is_active:
            raise ValidationError(
                "This campus is already inactive."
            )

        if campus.buildings.active().exists():
            raise ValidationError(
                "Campus cannot be deactivated while it "
                "has active buildings."
            )
        
        from apps.assignments.services.commitment_queries import (
            campus_has_unresolved_commitments,
        )

        if campus_has_unresolved_commitments(campus_id=campus.pk):
            raise ValidationError(
                "Campus cannot be deactivated while it has unresolved "
                "accommodation commitments."
            )

        campus.is_active = False

        return CampusService._save_campus(campus)