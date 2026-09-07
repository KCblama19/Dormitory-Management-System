from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django_countries.fields import CountryField

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

from datetime import date

# The student Department
class Department(TimeStampModel):
    name = models.CharField(
        _("Department name"),
        max_length=255,
        help_text=_("Full name of the department (e.g., 'Department of Computer Science').")
    )
    
    code = models.CharField(
        _("Department code"),
        max_length=10, unique=True,
        db_index=True,
        help_text=_("Unique identifier code (e.g., 'CS', 'BUS', 'SE').")
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
        
# The Student Major        
class Major(TimeStampModel): 
    name = models.CharField(
        _("Major name"),
        max_length=150,
        help_text=_("Full name of the major (e.g., 'Bachelor of Science in Computer Science').")
    )    
    code = models.CharField(
        _("major code"),
        max_length=10, unique=True,
        db_index=True,
        help_text=_("Unique identifier (e.g., 'BSC-CS', 'BSC-SE').")
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
        
        constraint = models.UniqueConstraint(
            fields=['name', 'department'],
            name="unique_major_name_per_department"
        )

    def __str__(self):
        return f"{self.code}: {self.name}"
    
    
class Degree(TimeStampModel):
    class AcademicLevel(models.TextChoices):
        UNDERGRADUATE = "UG", _("UNDERGRADUATE")
        POSTGRADUATE = "PG", _("Postgraduate (Master\'s)")
        DOCTORATE = "DOC", _("Doctorate (PhD)")
    
    class DegreeType(models.TextChoices):
        BA = "BA", _("Bachelor of Arts")
        BSC = "BSC", _("Bachelor of Science")
        BENG = "BENG", _("Bachelor of Engineering")
        MA = "MA", _("Master of Arts")
        MSC = "MSC", _("Master of Science")
        MBA = "MBA", _("Master of Business Administration")
        PHD = "PHD", _("Doctor")
        OTHER = "OTHER", _("Other degree type")

    name = models.CharField(
        max_length=10,
        choices=DegreeType,
        default=_("No Degree Selected")
        help_text=_("Name of the degree")
    )
    other_degree_type = models.CharField(
        max_length=100, 
        blank=True,
        null=False
        help_text=_("Name of the degree")
    )
    academic_level = models.CharField(
        max_length=3,
        choices=AcademicLevel,
        null=False,
        blank=False
        help_text=_("Bachelor, Masters, or PHD")
    )
    

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
        related_name="student_profile")
    
    student_id = models.CharField(
        max_length=10,
        unique=True,
        null=False
    )
    first_name = models.CharField(
        max_length=50
    )
    middle_name = models.CharField(
        max_length=50,
        blank=True,
    )
    last_name = models.CharField(
        max_length=50
    )
    gender = models.CharField(
        choices=Gender,
        null=False,
        blank=False,
    )
    nationality = CountryField(
        blank_label='(select country)'
    )
    # Are they a Art, Science, Eng, etc student?
    degree_type = models.ForeignKey(
        Degree,
        on_delete=models.PROTECT,
        related_name="students"
    )
    # What are they majoring specifically?
    major = models.ForeignKey(
        Major,
        on_delete=models.PROTECT,
        related_name="students"
    )
    # Is the student admitted to the university?
    academic_status = models.CharField(
        choices=AdmissionStatus,
        default=AdmissionStatus.PENDING
    )
    # Are they allow to have a room on campus?
    eligibility_status = models.CharField(
        choices=EligibilityStatus,
        default=EligibilityStatus.PENDING
    )  
    bio = models.TextField(
        max_length=300,
        null=True
        help_text=_("A short introduction of the student")
    )
    # Date the student arrive at the university
    university_arrival_date = models.DateField()
    expected_graduation_date = models.DateField(blank=False, null=False)
    
    # Derived Fields
    @property
    def full_name(self):
        """ Generate the full name of the student """
        if not self.middle_name:
            return f"{self.first_name} {self.last_name}"
            
        return f"{self.first_name} {self.middle_name} {self.last_name} "
    
    def can_book(self):
        """ Derived from:
            StudentProfile
                admission_status
                eligibility_status

            User
                account_status
                is_active

            StudentCampusAssignment
                current campus

            Booking system
                booking period / allocation rules
        """
    
    @property
    def academic_year(self):
        """Calculates what numerical year of study the student is in."""
        current_year = date.today().year
        start_year = self.arrival_date.year
        # Add 1 so their first year equals 1, not 0
        calculated_year = (current_year - start_year) + 1
        return max(1, calculated_year) # Ensures it never returns 0 or negative numbers

    @property
    def study_stage(self):
        """Returns the human-readable study_stage based on their academic tier and year."""
        # 1. First, check if they are an Undergraduate (UG)
        if self.degree_type.academic_tier == 'UG':
            undergrad_map = {
                1: "Freshman",
                2: "Sophomore",
                3: "Junior",
                4: "Senior"
            }
            # Fallback to "Senior+" if they are taking longer than 4 years
            return undergrad_map.get(self.academic_year, "Senior+")
            
        # 2. Handle Postgraduate (PG / Master's)
        elif self.degree_type.academic_tier == 'PG':
            return f"Master's Candidate (Year {self.academic_year})"
            
        # 3. Handle Doctorate (PHD)
        elif self.degree_type.academic_tier == 'PHD':
            return f"PhD Candidate (Year {self.academic_year})"
            
        return "Student"
    
    def clean(self):
        
    def save(self, **args, **kwargs,):
        
    def __str__(self):
        return f"{self.full_name} | {self.study_stage}"