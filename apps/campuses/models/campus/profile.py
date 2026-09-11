from django.db import models
from django.utils.translation import gettext_lazy as _

# Extensions
from django_countries.fields import CountryField

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

"""
This Model represents a physical campus belonging to a 
university.

A university may have multiple campuses, and campuses may
be located in different countries or administrative regions
"""

class Campus(TimeStampModel):
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
        _("Campus Name Abbreviation"),
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