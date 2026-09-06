from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from django_countries.fields import CountryField

from datetime import date

class Major(models.Model):
    # e.g: "Software Engineering" 
    name = models.CharField(max_length=100, unique=True) 
    # e.g: "SE"
    code = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    
class DegreeType(models.Model):
    class AcademicLevel(models.TextChoices):
        UNDERGRADUATE = "UG", "UNDERGRADUATE"
        POSTGRADUATE = "PG", "Postgraduate (Master\'s)"
        DOCTORATE = "DOC", "Doctorate (PhD)"
    
    degree_type = [
        ("BA", "Bachelor of Arts"),
        ("BSC", "Bachelor of Science"),
        ("BENG", "Bachelor of Engineering"),
        ("MA", "Master of Arts"),
        ("MSC", "Master of Science"),
        ("MBA", "Master of Business Administration"),
        ("PHD", "Doctor"),
        ("OTHER", "Other degree type"),
    ]
    
    name = models.CharField(
        max_length=10,
        choices=degree_type,
        default="No Degree Selected"
    )
    other_degree_type = models.CharField(
        max_length=100, 
        blank=True,
        null=False
    )
    academic_level = models.CharField(
        max_length=3,
        choices=AcademicLevel,
        null=False,
        blank=False
    )
    

class Student(models.Model):
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
        
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile")
    
    student_id = models.CharField(
        max_length=10,
        unique=True,
        null=False)
    
    first_name = models.CharField(
        blank=False,
        null=False
    )
    middle_name = models.CharField(
        blank=True,
        null=True
    )
    last_name = models.CharField(
        blank=False,
        null=False
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
        DegreeType,
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
        max_length=200,
        null=True
    )
    # Date the student arrive at the university
    university_arrival_date = models.DateField()
    
    expected_graduation_date = models.DateField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def full_name(self):
        """ Generate the full name of the student """
        if not self.middle_name:
            return f"{self.first_name} {self.last_name}"
            
        return f"{self.first_name} {self.middle_name} {self.last_name} "
    
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
    
    def __str__(self):
        return f"{self.full_name} | {self.study_stage}"