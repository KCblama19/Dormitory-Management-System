from django.db import models
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.core.abstract_models.timestamp_models import TimeStampModel
from apps.core.abstract_models.gender_model import Gender

# Dormitory Models
from apps.accommodation.models.building.building_model import Building


class Staff(TimeStampModel):
    """
    Represents a staff member responsible for the day-to-day management
    of a dormitory building.

    A staff member belongs to exactly one building and has one of two
    responsibilities:

    - Building Manager: Full operational and configuration authority
      over the assigned building.
    - Building Staff: Operational authority, but no configuration
      authority.

    Authentication and account credentials are handled by the project's
    User model. This model only stores staff-specific information.
    """

    class Role(models.TextChoices):
        BUILDING_MANAGER = "BUILDING_MANAGER", _("Building Manager")
        BUILDING_STAFF = "BUILDING_STAFF", _("Building Staff")

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        INACTIVE = "INACTIVE", _("Inactive")
        SUSPENDED = "SUSPENDED", _("Suspended")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="staff_profile",
        verbose_name=_("user"),
        help_text=_("The user account associated with this staff profile."),
    )
    staff_id = models.CharField(
        _("Staff ID"),
        max_length=10,
        unique=True,
        db_index=True,
        help_text=_("Unique institutional staff identifier."),
    )
    first_name = models.CharField(
        _("Staff first name"),
        max_length=50,
    )
    middle_name = models.CharField(
        _("Staff middle name"),
        max_length=50,
    )
    last_name = models.CharField(
        _("Staff last name"),
        max_length=50,
    )
    gender = models.ForeignKey(
        Gender,
        max_length=3,
        verbose_name=_("Staff Gender"),
        on_delete=models.PROTECT,
        related_name="staffs"
    )
    building = models.ForeignKey(
        "accommodation.Building",
        on_delete=models.PROTECT,
        related_name="staff_members",
        verbose_name=_("building"),
        help_text=_("The dormitory building this staff member manages."),
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BUILDING_STAFF,
        verbose_name=_("role"),
        help_text=_("The staff member's level of responsibility."),
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("status"),
        help_text=_("Whether the staff member is currently active."),
    )

    class Meta:
        ordering = ["building", "role", "user"]
        verbose_name = _("staff member")
        verbose_name_plural = _("staff members")
        constraints = [
            models.UniqueConstraint(
                fields=["building"],
                condition=Q(
                    role="BUILDING_MANAGER",
                    status="ACTIVE",
                ),
                name="unique_active_building_manager",
            ),
        ]
        indexes = [
            models.Index(
                fields=["building", "status"],
                name="staff_building_status_idx",
            ),
            models.Index(
                fields=["building", "role"],
                name="staff_building_role_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} - {self.building}"
    
    # Derived Fields
    @property
    def full_name(self):
        names = [
            self.first_name,
            self.middle_name,
            self.last_name
        ]
        
        return " ".join(
            name for name in names if name
        ).strip()