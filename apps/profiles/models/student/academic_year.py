from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

"""
This Model tracks the university operational calendar session, 
start/end dates, and active school year status

    - Primary Function: Represents a specific academic 
      calendar session (e.g., 2025/2026, 2026/2027).

    - Key Features:
        - Defines operational timeframes using 
          start_date and end_date.
          
        - Tracks active status via an is_current 
          boolean flag, enforced by a UniqueConstraint 
          so only one academic year can be marked as 
          current at any time.
"""

class AcademicYear(TimeStampModel):

    name = models.CharField(
        _("Academic year"),
        max_length=20,
        unique=True,
        help_text=_(
            "Academic year name "
            "(e.g., '2026/2027')."
        )
    )

    start_date = models.DateField(
        _("Start date")
    )

    end_date = models.DateField(
        _("End date")
    )

    is_current = models.BooleanField(
        _("Current academic year"),
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Academic Year")
        verbose_name_plural = _("Academic Years")

        constraints = [
            models.UniqueConstraint(
                fields=["is_current"],
                condition=models.Q(is_current=True),
                name="only_one_current_academic_year"
            )
        ]

    def clean(self):
        super().clean()

        if self.end_date <= self.start_date:
            raise ValidationError({
                "end_date": _(
                    "Academic year end date must be after "
                    "the start date."
                )
            })

    def __str__(self):
        return self.name