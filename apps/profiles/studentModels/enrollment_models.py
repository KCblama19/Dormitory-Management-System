from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Models and Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel
from apps.profiles.studentModels.student_models import Student
from apps.profiles.studentModels.program_models import Program
from apps.profiles.studentModels.academic_year_models import AcademicYear

"""
This Model tracks what a student is studying and 
their academic status for each academic year.

    - Primary Function: Connects a Student 
      to a specific Program (e.g., Computer Science) 
      and an AcademicYear (e.g., 2026/2027).

    - Key Features:
        - Status & Stage: Tracks whether the student 
          is currently ACTIVE, COMPLETED, SUSPENDED, 
          WITHDRAWN, or DEFERRED, as well as their 
          year_of_study (e.g., Year 1, Year 2).

    - Primary Enrollment Flag (is_primary): Distinguishes 
      a student's main program from secondary programs 
      (which allows support for dual-degree or minor 
      programs without breaking single-program rules).
      
    - Dates: Captures the start date, end date, and 
      expected graduation date for record-keeping.
"""



class StudentEnrollment(TimeStampModel):

    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        COMPLETED = "COMPLETED", _("Completed")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")
        SUSPENDED = "SUSPENDED", _("Suspended")
        DEFERRED = "DEFERRED", _("Deferred")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments"
    )

    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="student_enrollments"
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="student_enrollments"
    )

    # Identifies the student's primary/current academic program.
    is_primary = models.BooleanField(
        _("Primary enrollment"),
        default=True,
        help_text=_(
            "Identifies whether this is the student's "
            "primary academic program."
        )
    )

    year_of_study = models.PositiveSmallIntegerField(
        _("Year of study"),
        blank=True,
        null=True,
        help_text=_(
            "Academic year within the student's program. "
            "Not applicable to every type of program."
        )
    )

    enrollment_status = models.CharField(
        _("Enrollment status"),
        max_length=20,
        choices=EnrollmentStatus,
        default=EnrollmentStatus.ACTIVE
    )

    start_date = models.DateField(
        _("Enrollment start date")
    )

    end_date = models.DateField(
        _("Enrollment end date"),
        blank=True,
        null=True
    )

    expected_graduation_date = models.DateField(
        _("Expected graduation date"),
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Student Enrollment")
        verbose_name_plural = _("Student Enrollments")

        constraints = [
            # A student may have multiple enrollments in the
            # same academic year for special cases such as
            # dual-degree or pilot programs, but only one can be
            # the primary active enrollment.
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=(
                    models.Q(
                        enrollment_status="ACTIVE",
                        is_primary=True
                    )
                ),
                name="one_primary_active_enrollment_per_year"
            ),

            models.CheckConstraint(
                condition=models.Q(year_of_study__gte=1),
                name="year_of_study_must_be_positive"
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
                    "Enrollment end date must be after "
                    "the enrollment start date."
                )
            })

        if (
            self.expected_graduation_date
            and self.start_date
            and self.expected_graduation_date <= self.start_date
        ):
            raise ValidationError({
                "expected_graduation_date": _(
                    "Expected graduation date must be after "
                    "the enrollment start date."
                )
            })

        # Language and other non-degree programs do not
        # necessarily have a meaningful year of study.
        if (
            self.program
            and self.program.program_type
            == Program.ProgramType.LANGUAGE
            and self.year_of_study is not None
        ):
            raise ValidationError({
                "year_of_study": _(
                    "Year of study should normally be empty "
                    "for language programs."
                )
            })

        # A completed, withdrawn, suspended, or deferred
        # enrollment should not be marked as the primary
        # active enrollment.
        if (
            self.is_primary
            and self.enrollment_status
            != self.EnrollmentStatus.ACTIVE
        ):
            raise ValidationError({
                "is_primary": _(
                    "Only an active enrollment can be "
                    "marked as the primary enrollment."
                )
            })

    def __str__(self):
        return (
            f"{self.student.student_id} | "
            f"{self.program.code} | "
            f"{self.academic_year}"
        )
