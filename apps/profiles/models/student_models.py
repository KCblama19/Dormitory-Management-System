from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django_countries.fields import CountryField

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

from datetime import date

"""
This file consist of the:
    - Department Model (Describes the student Department)
    - Degree Model (Describes the the type of degree
    (BSC, MSC, PHD)),
    - Major Model (Describe the student specialization),
    - Academic Year Model (Defines the universit's 
    academic calendar),
    - StudentAssignCampus Model (Record of the campus
    the student is currently assigned),
    - StudentEnrollment Model, (Describes their academic 
    program over time)
    - Student Model (This identifies the person)
"""


# The student Department
class Department(TimeStampModel):
    name = models.CharField(
        _("Department name"),
        max_length=255,
        help_text=_(
            "Full name of the department"
            "(e.g., 'Department of Computer Science')."
        ),
    )
    
    code = models.CharField(
        _("Department code"),
        max_length=10, 
        unique=True,
        db_index=True,
        help_text=_(
            "Unique identifier code (e.g., 'CS', 'BUS', 'SE')."
        )
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ["code"]
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
    
    def __str__(self):
        return f"{self.code}: {self.name}"
        
# The Student Major or Specialty     
class Major(TimeStampModel): 
    name = models.CharField(
        _("Major name"),
        max_length=150,
        help_text=_(
            "Full name of the major" 
            "(e.g., 'Computer Science')."
        )
    )    
    code = models.CharField(
        _("major code"),
        max_length=10, unique=True,
        db_index=True,
        help_text=_(
            "Unique identifier, e.g., 'CS', 'SE', 'IT'."
        ),
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
        verbose_name = _("major")
        verbose_name_plural = _("majors")
        
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'department'],
                name="unique_major_name_per_department",
            ),
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"
    
# The student Degree type (MSC, BSC, PHD)
class Degree(TimeStampModel):
    class AcademicLevel(models.TextChoices):
        UNDERGRADUATE = "UG", _("Undergraduate")
        POSTGRADUATE = "PG", _("Postgraduate")
        DOCTORATE = "DOC", _("Doctorate")
    
    class DegreeType(models.TextChoices):
        BA = "BA", _("Bachelor of Arts")
        BSC = "BSC", _("Bachelor of Science")
        BENG = "BENG", _("Bachelor of Engineering")
        MA = "MA", _("Master of Arts")
        MSC = "MSC", _("Master of Science")
        MBA = "MBA", _("Master of Business Administration")
        PHD = "PHD", _("Doctor of Philosophy")
        OTHER = "OTHER", _("Other degree type")
        
    code = models.CharField(
        _("Degree Code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique degree identifier, e.g. 'BSC', 'MSC', 'PHD'."
        )
    )
    degree_type = models.CharField(
        _("Degree type"),
        max_length=10,
        choices=DegreeType,
        help_text=_("Name of the degree")
    )
    other_degree_type = models.CharField(
        _("Other degree type"),
        max_length=100, 
        blank=True,
        help_text=_("Name of the degree")
    )
    academic_level = models.CharField(
        max_length=3,
        choices=AcademicLevel,
        help_text=_("Bachelor, Masters, or PHD")
    )
    duration_years = models.PositiveSmallIntegerField(
        _("Standard duration"),
        help_text=_(
            "Standard number of years require to complete the degree"
        )
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ["academic_level", "degree_type"] 
        verbose_name = _("Degree")
        verbose_name_plural = _("Degrees")
        
    def __str__(self):
        return self.get_degree_type_display()
    
# The student Academic year (e.g., 2026/2027)
class AcademicYear(TimeStampModel):
    
    name = models.CharField(
        _("Academic year"),
        max_length=20,
        unique=True,
        help_text=_(
            "Display name, e.g., '2026/2027'."
        ),
    )
    
    start_date = models.DateField(
        _("Start date"),
    )
    
    end_date = models.DateField(
        _("End date")
    )
    
    is_current = models.BooleanField(
        _("Current academic year"),
        default=False,
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
                name="only_one_current_academic_year",
            )
        ]
        
    def clean(self):
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        if self.end_date <= self.start_date:
            raise ValidationError({
                "end_date": _(
                    "Academic year end date must be "
                    "less than or equal to the start date."
                )
            })
    
    def __str__(self):
        return self.name

# The student Academic Enrollment Data
class StudentEnrollment(TimeStampModel):
    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        COMPLETED = "COMPLETED", _("Completed")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")
        SUSPENDED = "SUSPENDED", _("Suspended")
        DEFERRED = "DEFERRED", _("Deferred")
        
    student = models.ForeignKey(
        "Student",
        on_delete=models.CASCADE,
        related_name="enrollment",
    )
    # The current Academic year e.g.,2026/2027
    academic_year = models.ForeignKey(
        "AcademicYear",
        on_delete=models.PROTECT,
        related_name="student_enrollments",
    )
    # Are they Bsc, Msc, PhD student?
    degree = models.ForeignKey(
        "Degree",
        on_delete=models.PROTECT,
        related_name="student_enrollments"
    )
    # What are they majoring specifically?
    major = models.ForeignKey(
        "Major",
        on_delete=models.PROTECT,
        related_name="student_enrollments"
    )
    year_of_study = models.PositiveSmallIntegerField(
        _("Year of study"),
        help_text=_(
            "The student's academic year within the program, "
            "e.g. 1, 2, 3, 4."
        ),
    )
    enrollment_status = models.CharField(
        _("Enrollment Status"),
        max_length=20,
        choices=EnrollmentStatus,
        default=EnrollmentStatus.ACTIVE,
    )
    start_date = models.DateField(
        _("Enrollment start date"),
    )
    end_date = models.DateField(
        _("Enrollment end date"),
        blank=True,
        null=True,
    )
    expected_graduation_date = models.DateField(
        _("Expected graduation date"),
        blank=True,
        null=True,
    )
    
    # Date the student arrive at the university
    university_arrival_date = models.DateField(
        _("University arrival date"),
    )
    
    class Meta:
        ordering = ["-academic_year__start_date"]
        
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year",],
                name="unique_student_enrollment_per_academic_year",
            ),
            
            models.CheckConstraint(
                condition=models.Q(year_of_study__gte=1),
                name="year_of_study_must_be_positive",
            ),
        ]
        
    def __str__(self):
        return (
            f"{self.student.student.id} — "
            f"{self.academic_year} — "
            f"{self.major.name}"
        )

# The student Current and Past Assign Campus
class StudentCampusAssignment(TimeStampModel):

    class AssignmentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        ENDED = "ENDED", _("Ended")
        TRANSFERRED = "TRANSFERRED", _("Transferred")

    student = models.ForeignKey(
        "Student",
        on_delete=models.CASCADE,
        related_name="campus_assignments",
    )
    campus = models.ForeignKey(
        "Campus",
        on_delete=models.PROTECT,
        related_name="student_assignments",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="campus_assignments",
    )

    start_date = models.DateField(
        _("Assignment start date"),
    )
    end_date = models.DateField(
        _("Assignment end date"),
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("Assignment status"),
        max_length=20,
        choices=AssignmentStatus,
        default=AssignmentStatus.ACTIVE,
    )

    reason = models.CharField(
        _("Assignment reason"),
        max_length=255,
        blank=True,
        help_text=_(
            "Optional explanation for the assignment or transfer."
        ),
    )

    class Meta:
        ordering = ["-start_date"]

        indexes = [
            models.Index(
                fields=["student", "status"],
            ),
            models.Index(
                fields=["campus", "status"],
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()

        if (
            self.end_date
            and self.end_date <= self.start_date
        ):
            raise ValidationError({
                "end_date": _(
                    "End date must be after the start date."
                )
            })

    def __str__(self):
        return (
            f"{self.student.student_id} — "
            f"{self.campus.name}"
        )
    
class Student(TimeStampModel):
    
    # Enumerators
    class Gender(models.TextChoices):
        MALE = "M", _("Male")
        FEMALE = "F", _("Female")

    class EligibilityStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending Review") 
        ELIGIBLE = "ELIGIBLE", _("Eligible")
        INELIGIBLE = "INELIGIBLE", _("Ineligible")
        SUSPENDED = "SUSPENDED", _("Suspended / Disciplinary Action")
        
    class AdmissionStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ACCEPTED = "ACCEPTED", _("Accepted")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")
        REJECTED = "REJECTED", _("Rejected")
    
    # Model Fields 
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student")
    
    student_id = models.CharField(
        _("Student ID"),
        max_length=10,
        unique=True,
        db_index=True,
    )
    first_name = models.CharField(
        _("First name"),
        max_length=50,
    )
    middle_name = models.CharField(
        _("Middle name"),
        max_length=50,
        blank=True,
    )
    last_name = models.CharField(
        _("Last name"),
        max_length=50,
    )
    gender = models.CharField(
        _("Gender"),
        max_length=1,
        choices=Gender,
    )
    nationality = CountryField(
        _("Nationality"),
        blank_label='(select country)',
    )
    # Is the student admitted to the university?
    admission_status = models.CharField(
        _("Admission status"),
        max_length=20,
        choices=AdmissionStatus,
        default=AdmissionStatus.PENDING,
    )
    # Are they allow to have a room on campus?
    eligibility_status = models.CharField(
        _("ELigibility status"),
        max_length=20,
        choices=EligibilityStatus,
        default=EligibilityStatus.PENDING,
    )  
    bio = models.TextField(
        _("Bio"),
        max_length=300,
        blank=True,
        help_text=_("A short introduction of the student"),
    )
    
    # Derived Fields
    @property
    def full_name(self):
        """ Generate and Return the full name of the student """
        names = [
            self.first_name,
            self.middle_name,
            self.last_name,
        ]
            
        return " ".join(name for name in names if name).strip()
    
    def clean(self):
        """ Validate relationships and date-dependent date."""
        super().clean()
        
        if (
            self.expected_graduation_date
            and self.university_arrival_date
            and self.expected_graduation_date
            <= self.university_arrival_date
        ):
            raise ValidationError({
                "expected_graduation_date": _(
                    "Expected graduation date must be no" 
                    "less than the university arrival date."
                )
            })
        
    def __str__(self):
        return f"{self.student_id} — {self.full_name}"