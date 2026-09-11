from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

class Department(TimeStampModel):
    name = models.CharField(
        _("Department name"),
        max_length=255,
        help_text=_(
            "Full name of the department "
            "(e.g., 'Department of Computer Science')."
        )
    )

    code = models.CharField(
        _("Department code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique identifier code "
            "(e.g., 'CS', 'BUS', 'SE')."
        )
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self):
        return f"{self.code}: {self.name}"
