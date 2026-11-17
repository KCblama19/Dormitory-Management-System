from django.db import models
from django.utils.translation import gettext_lazy as _

# Extensions
from django_countries.fields import CountryField

# TimeZone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ValidationError

# Abstract Models
from apps.core.abstract_models.timestamp_models import TimeStampModel

# Managers
from apps.accommodations.models.managers.campusQuerySet import CampusQuerySet

def validate_iana_timezone(value: str) -> None:
    """Validate that Python can load the configured IANA timezone."""
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValidationError(
            _("Enter a valid IANA timezone, such as Asia/Shanghai."),
            code="invalid_timezone",
        ) from exc

class Campus(TimeStampModel):
    """
    This Model represents a physical campus belonging to a 
    university.

    A university may have multiple campuses, and campuses may
    be located in different countries or administrative regions
    """
    
    university = models.ForeignKey(
        "university.University",
        on_delete=models.PROTECT,
        related_name="campuses",
        db_index=True,
    )
    name = models.CharField(
        _("Campus Name"),
        max_length=255,
    )
    code = models.CharField(
        _("Campus Code"),
        max_length=20,
    )
    postal_code = models.CharField(
        _("Postal/ZIP Code"),
        max_length=20,
        blank=True,
    )
    address = models.TextField(
        help_text=_(
            "Enter the full street address, building number, or suite."
        ),
    )
    city = models.CharField(
        _("City of the Campus"),
        max_length=100,
        help_text=_(
            "Enter the City the campus is located in."
        ),
    )
    province = models.CharField(
        _("Province/State/County"),
        max_length=100,
    )
    country = CountryField(
        _("University Country"),
        blank_label="Select Country",
    )
    timezone = models.CharField(
        _("Campus Timezone"),
        max_length=64,
        validators=[validate_iana_timezone],
        help_text=_(
            "Enter the IANA timezone used for campus deadlines, "
            "such as Asia/Shanghai."
        ),
    )
    description = models.TextField(
        blank=True,
        help_text=_(
            "A brief overview or history of the campus"
            )
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
    )
    
    objects = CampusQuerySet.as_manager()
    
    class Meta:
        ordering = ["name"]
        verbose_name = _("Campus")
        verbose_name_plural = _("Campuses")
        
        constraints = [
            models.UniqueConstraint(
                fields=["university", "name"],
                name="unique_campus_name_per_university",
            ),
            models.UniqueConstraint(
                fields=["university", "code"],
                name="unique_campus_code_per_university",
            )
        ]
        
    def __str__(self):
        return (
            f"{self.university.name} - {self.name}"
            f"({self.city}, {self.province}, {self.country.name})"
        )    