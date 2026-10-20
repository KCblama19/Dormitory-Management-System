from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.staff.models.staff_models import Staff

# POLICIES
from apps.core.policies import StaffPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    PermissionDenied,
)


class StaffService:

    @staticmethod
    @transaction.atomic
    def create_staff(
        *,
        actor,
        user,
        building,
        role: str=Staff.Role.BUILDING_STAFF,
    ):
        """
        
        """
        if not StaffPolicy.can_create_staff(
            actor,
            building,
        ):
            raise PermissionDenied(
                "This action is reserve for admin and "
                "or the building manager of this building."
            )
            
        if not user.is_staff_member:
            raise ValidationError(
                "User account must have STAFF account type."
            )

        if hasattr(user, "staff_profile"):
            raise ConflictError(
                "This user already has a staff profile."
            )

        if role not in {
            Staff.Role.BUILDING_MANAGER,
            Staff.Role.BUILDING_STAFF,
        }:
            raise ValidationError(
                "Invalid staff role."
            )

        if (
            role == Staff.Role.BUILDING_MANAGER
            and Staff.objects
            .managers_for_building(building)
            .exists()
        ):
            raise ConflictError(
                "This building already has an active manager."
                "There can be one building manager per building."
            )

        staff = Staff(
            user=user,
            building=building,
            role=role,
            status=Staff.Status.ACTIVE,
        )

        try:
            staff.full_clean()
            staff.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return staff

    @staticmethod
    @transaction.atomic
    def assign_staff_to_building(
        *,
        actor,
        staff,
        building,
        role=None,
    ):
        """
        
        """
        if not StaffPolicy.can_assign_staff_to_building(
            actor, staff,
        ):
            raise PermissionDenied(
                "This action is reserve for admin"
            )

        target_role = role or staff.role

        if (
            target_role == Staff.Role.BUILDING_MANAGER
            and Staff.objects
            .managers_for_building(building)
            .exclude(pk=staff.pk)
            .exists()
        ):
            raise ConflictError(
                "The target building already has an active manager."
            )

        staff.building = building
        staff.role = target_role
        staff.status = Staff.Status.ACTIVE

        staff.full_clean()
        staff.save(
            update_fields=[
                "building",
                "role",
                "status",
            ]
        )

        return staff

    @staticmethod
    @transaction.atomic
    def change_role(
        *,
        actor,
        staff,
        role,
    ):
        if not StaffPolicy.can_change_staff_role(
            actor, staff,
        ):
            raise PermissionDenied(
                "This action is reserve for admin"
            )

        if role not in {
            Staff.Role.BUILDING_MANAGER,
            Staff.Role.BUILDING_STAFF,
        }:
            raise ValidationError(
                "Invalid staff role."
            )

        if (
            role == Staff.Role.BUILDING_MANAGER
            and staff.role != Staff.Role.BUILDING_MANAGER
            and Staff.objects
            .managers_for_building(staff.building)
            .exclude(pk=staff.pk)
            .exists()
        ):
            raise ConflictError(
                "This building already has an active manager."
            )

        staff.role = role

        staff.full_clean()
        staff.save(update_fields=["role"])

        return staff

    @staticmethod
    @transaction.atomic
    def activate_staff(*, actor, staff):
        
        if not StaffPolicy.can_activate_staff(
            actor, staff,
        ):
            raise PermissionDenied(
                "This action is reserved for admin and "
                "building manager of this building"
            )

        staff.status = Staff.Status.ACTIVE
        staff.user.is_active = True
        staff.user.accountStatus = "active"

        staff.full_clean()
        staff.user.full_clean()

        staff.save(update_fields=["status"])
        staff.user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )

        return staff

    @staticmethod
    @transaction.atomic
    def deactivate_staff(*, actor, staff):
        if not StaffPolicy.can_deactivate_staff(
            actor,
            staff,
        ):
            raise PermissionDenied(
                "This action is reserved for admin and the "
                "building manager of this building"
            )

        staff.status = Staff.Status.INACTIVE
        staff.user.is_active = False
        staff.user.accountStatus = "locked"

        staff.full_clean()
        staff.user.full_clean()

        staff.save(update_fields=["status"])
        staff.user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )

        return staff

    @staticmethod
    @transaction.atomic
    def transfer_staff(
        *,
        actor,
        staff,
        new_building,
        new_role=None,
    ):
        if not StaffPolicy.can_transfer_staff(
            actor,
            staff,
        ):
            raise PermissionDenied(
                "You do not have permission to assign staff "
                "to this building."
            )

        target_role = new_role or staff.role

        if (
            target_role == Staff.Role.BUILDING_MANAGER
            and Staff.objects
            .managers_for_building(new_building)
            .exclude(pk=staff.pk)
            .exists()
        ):
            raise ConflictError(
                "The target building already has an active manager."
            )

        staff.building = new_building
        staff.role = target_role
        staff.status = Staff.Status.ACTIVE

        staff.full_clean()
        staff.save(
            update_fields=[
                "building",
                "role",
                "status",
            ]
        )

        return staff