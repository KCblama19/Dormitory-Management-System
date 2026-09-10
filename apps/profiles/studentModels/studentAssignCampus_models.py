from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Models and Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel
from apps.profiles.studentModels.student_models import Student
from apps.profiles.studentModels.academic_year_models import AcademicYear


"""
This Model tracks where a student is physically 
located or assigned to study for each academic year.

    - Primary Function: Connects a Student to a 
      specific Campus and an AcademicYear.

    - Key Features:
        - Location History: Universities often 
          have multiple campuses (e.g., Main Campus, 
          International Campus, Branch Campus). 
          This model records where the student is based 
          during a specific period.
        
        - Status Tracking: Tracks whether the assignment 
          is ACTIVE, ENDED, or TRANSFERRED 
          (e.g., if a student changes campuses mid-degree).

        - Housing Eligibility Prerequisite: The systems 
          use this to verify which campus's housing/dormitories 
          a student is eligible to apply for in a given year
"""

class StudentAssignCampus(TimeStampModel):

    class AssignmentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        ENDED = "ENDED", _("Ended")
        TRANSFERRED = "TRANSFERRED", _("Transferred")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="campus_assignments"
    )

    campus = models.ForeignKey(
        "Campus",
        on_delete=models.PROTECT,
        related_name="student_assignments"
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="campus_assignments"
    )

    start_date = models.DateField(
        _("Assignment start date")
    )

    end_date = models.DateField(
        _("Assignment end date"),
        blank=True,
        null=True
    )

    status = models.CharField(
        _("Assignment status"),
        max_length=20,
        choices=AssignmentStatus,
        default=AssignmentStatus.ACTIVE
    )

    reason = models.CharField(
        _("Assignment reason"),
        max_length=255,
        blank=True,
        help_text=_(
            "Optional explanation for the assignment "
            "or transfer."
        )
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Student Campus Assignment")
        verbose_name_plural = _("Student Campus Assignments")

        constraints = [
            # A student should only have one active campus
            # assignment for an academic year.
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(
                    status="ACTIVE",
                ),
                name="one_active_campus_per_student_per_year"
            )
        ]

        indexes = [
            models.Index(
                fields=["student", "status"]
            ),
            models.Index(
                fields=["campus", "status"]
            )
        ]

    def clean(self):
        super().clean()

        if (
            self.end_date
            and self.end_date <= self.start_date
        ):
            raise ValidationError({
                "end_date": _(
                    "Assignment end date must be after "
                    "the assignment start date."
                )
            })

    def __str__(self):
        return (
            f"{self.student.student_id} | "
            f"{self.campus.name}"
        )
