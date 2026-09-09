from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Django Extensions
from django_countries.fields import CountryField

# Models and Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel
from apps.profiles.studentModels.program_models import Program
from apps.profiles.studentModels.degree_models import Degree
from apps.profiles.studentModels.studentAssignCampus_models import StudentAssignCampus
from apps.profiles.studentModels.enrollment_models import StudentEnrollment

"""
This Model tracks an individual student's personal 
identity profile, admission status, and 
campus housing eligibility state.

    - Primary Function: Serves as the central profile 
      for an individual student, holding personal 
      identification and housing eligibility states.

    - Key Features:
        - Links to the user account system and records 
          core personal details (names, gender, 
          nationality).

        - Tracks overall university admission status 
          and campus housing eligibility.

        - Provides quick access to a student's 
          active program, campus location, and 
          year of study for the current academic year.
"""

class Student(TimeStampModel):

    # Enumerators
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    class EligibilityStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        ELIGIBLE = "ELIGIBLE", "Eligible"
        INELIGIBLE = "INELIGIBLE", "Ineligible"
        SUSPENDED = "SUSPENDED", "Suspended / Disciplinary Action"

    class AdmissionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        REJECTED = "REJECTED", "Rejected"

    # Model Fields
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student"
    )

    student_id = models.CharField(
        _("Student ID"),
        max_length=30,
        unique=True,
        db_index=True
    )

    first_name = models.CharField(
        _("First name"),
        max_length=50
    )

    middle_name = models.CharField(
        _("Middle name"),
        max_length=50,
        blank=True
    )

    last_name = models.CharField(
        _("Last name"),
        max_length=50
    )

    gender = models.CharField(
        _("Gender"),
        max_length=1,
        choices=Gender
    )

    nationality = CountryField(
        _("Nationality"),
        blank_label="(select country)"
    )

    # Is the student admitted to the university?
    admission_status = models.CharField(
        _("Admission status"),
        max_length=20,
        choices=AdmissionStatus,
        default=AdmissionStatus.PENDING
    )

    # Are they allow to have a room on campus?
    eligibility_status = models.CharField(
        _("Housing eligibility"),
        max_length=20,
        choices=EligibilityStatus,
        default=EligibilityStatus.PENDING
    )

    bio = models.TextField(
        _("Bio"),
        max_length=300,
        blank=True,
        help_text=_(
            "A short introduction of the student."
        )
    )

    # Derived Fields
    @property
    def full_name(self):
        """Generate the full name of the student."""

        names = [
            self.first_name,
            self.middle_name,
            self.last_name
        ]

        return " ".join(
            name for name in names if name
        ).strip()

    @property
    def current_enrollment(self):
        """
        Return the student's current primary enrollment.

        The enrollment must:
            - belong to the current academic year
            - be active
            - be marked as primary
        """

        return (
            self.enrollments
            .filter(
                academic_year__is_current=True,
                enrollment_status=(
                    StudentEnrollment.EnrollmentStatus.ACTIVE
                ),
                is_primary=True
            )
            .select_related(
                "program",
                "program__degree",
                "program__major",
                "academic_year"
            )
            .first()
        )

    @property
    def current_campus_assignment(self):
        """
        Return the student's current active campus assignment.
        """

        return (
            self.campus_assignments
            .filter(
                academic_year__is_current=True,
                status=(
                    StudentAssignCampus
                    .AssignmentStatus.ACTIVE
                )
            )
            .select_related(
                "campus",
                "academic_year"
            )
            .first()
        )

    @property
    def current_campus(self):
        """Return the student's current campus."""

        assignment = self.current_campus_assignment

        if assignment:
            return assignment.campus

        return None

    @property
    def year_of_study(self):
        """
        Return the student's current year of study.

        Returns None when the student's current program
        does not use a year-of-study structure.
        """

        enrollment = self.current_enrollment

        if enrollment:
            return enrollment.year_of_study

        return None

    @property
    def study_stage(self):
        """
        Returns a human-readable description of the student's
        current academic stage.
        """

        enrollment = self.current_enrollment

        if not enrollment:
            return "Student"

        program = enrollment.program

        # Language and other non-degree students
        # do not necessarily have freshman/senior stages.
        if program.program_type != Program.ProgramType.DEGREE:
            return program.name

        year = enrollment.year_of_study

        if not year:
            return "Student"

        if program.degree.academic_level == (
            Degree.AcademicLevel.UNDERGRADUATE
        ):
            return f"Undergraduate Year {year}"

        if program.degree.academic_level == (
            Degree.AcademicLevel.POSTGRADUATE
        ):
            return f"Master's Year {year}"

        if program.degree.academic_level == (
            Degree.AcademicLevel.DOCTORATE
        ):
            return f"PhD Year {year}"

        return "Student"

    def can_book(self):
        """
        Determine whether the student is eligible to
        participate in the dormitory booking process.

        Final booking eligibility should be handled by
        the booking/eligibility service because it depends on:

            Student
                admission_status
                eligibility_status

            User
                account_status
                is_active

            StudentCampusAssignment
                current campus

            Booking system
                booking period
                allocation rules
                housing policies
        """

        return (
            self.admission_status
            == self.AdmissionStatus.ACCEPTED
            and self.eligibility_status
            == self.EligibilityStatus.ELIGIBLE
        )

    def clean(self):
        super().clean()

    def save(self, **kwargs):
        self.full_clean()
        super().save(**kwargs)

    def __str__(self):
        return f"{self.student_id} | {self.full_name}"