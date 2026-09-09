from django.db import models
from django.utils.translation import gettext_lazy as _

# Models and Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel
from apps.profiles.studentModels.department_models import Department

"""
This Model tracks a specific field of academic 
specialization offered under a single department.

    - Primary Function: Represents a specific field 
      of specialization (e.g., Software Engineering, 
      Finance, Mechanical Engineering).

    - Key Features:
        - Links directly to a Department via 
          ForeignKey(Department, on_delete=models.PROTECT).
          
        - Includes a unique constraint on (name, 
          department) to ensure majors aren't 
          duplicated within the same department.
"""
class Major(TimeStampModel):
    name = models.CharField(
        _("Major name"),
        max_length=150,
        help_text=_(
            "Full name of the major "
            "(e.g., 'Computer Science')."
        )
    )

    code = models.CharField(
        _("Major code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique identifier "
            "(e.g., 'CS', 'SE', 'IT')."
        )
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="majors"
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Major")
        verbose_name_plural = _("Majors")

        constraints = [
            models.UniqueConstraint(
                fields=["name", "department"],
                name="unique_major_name_per_department"
            )
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"
