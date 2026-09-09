from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.abstract_models.timestamp_models import TimeStampModel

""""
Tracks the formal qualification, degree level, and 
standard completion duration awarded by the university.

    - Primary Function: Represents the qualification 
      or award level conferred upon completion 
      (e.g., Bachelor of Science, Master of Arts).

    - Key Features:
        - Stores standard metadata such as 
          duration_years and an AcademicLevel 
          enum (UG for Undergraduate, 
          PG for Postgraduate, DOC for Doctorate).
          
        - Referenced by degree-bearing Program models 
          to establish degree rules.
"""
class Degree(TimeStampModel):

    class AcademicLevel(models.TextChoices):
        UNDERGRADUATE = "UG", _("Undergraduate")
        POSTGRADUATE = "PG", _("Postgraduate")
        DOCTORATE = "DOC", _("Doctorate")

    code = models.CharField(
        _("Degree code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique institutional identifier for the degree "
            "(e.g., 'BSC', 'MSC', 'PHD')."
        )
    )

    name = models.CharField(
        _("Degree name"),
        max_length=150,
        help_text=_(
            "Full name of the degree "
            "(e.g., 'Bachelor of Science')."
        )
    )

    academic_level = models.CharField(
        _("Academic level"),
        max_length=3,
        choices=AcademicLevel,
        help_text=_(
            "Academic level of the degree."
        )
    )

    duration_years = models.PositiveSmallIntegerField(
        _("Standard duration"),
        blank=True,
        null=True,
        help_text=_(
            "Standard number of years required to complete "
            "the degree."
        )
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["academic_level", "code"]
        verbose_name = _("Degree")
        verbose_name_plural = _("Degrees")

    def __str__(self):
        return f"{self.code}: {self.name}"