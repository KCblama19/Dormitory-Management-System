from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from accounts.manager import UserManager
from django.core.validators import validate_email
import uuid

class User(AbstractUser):
    """
    Custom User model designed for controlled identity systems.

    Key design principles:
    - Users are PROVISIONED by admin (no public registration)
    - Multiple identifiers supported (student_id, email, phone)
    - Authentication still uses Django's `username` internally

    Identifier strategy:
    - Students → username is system-generated (NOT student_id)
    - Staff/Admin → username is system-generated

    This allows:
    - Flexible login (via custom backend later)
    - Compatibility with Django auth system
    """

    class UserType(models.TextChoices):
        STUDENT = "STUDENT", _("Student")
        STAFF = "STAFF", _("Staff")
        ADMIN = "ADMIN", _("Administrator")
        
    class AccountStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        LOCKED = "locked", _("Locked")
        SUSPENDED = "suspended", _("Suspended")
        
        
    # -------------------------
    # Core Identity Fields
    # -------------------------
    
    # A unique uuid assign to the user,
    # for data integrity and uniqueness
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        editable=False    
    )
    
    """
    Override the username field to be flexible 
    It will be generated if no username was given
    """
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    
    # Student-specific identifier (optional for staff/admin)
    student_id = models.CharField(
        _("student ID"),
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Unique student identifier for student users"),
    )
    
    staff_id = models.CharField(
        _("staff ID"),
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Unique identifier for staff or admin users")
    )

    # Email is required for staff/admin login
    email = models.EmailField(
        _("email address"),
        unique=True,
        null=True,  # Allow null for students without email
        blank=True,
        validators=[validate_email]
    )
    
    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        unique=True,
        null=True,
        blank=True,
    )

    # Role determines user behavior and permissions
    role = models.CharField(
        max_length=20,
        choices=UserType.choices,
        help_text=_("Designates the role and permission of the user in the system"),
    )
    
    # ---------------------------------
    # Verification / Activation Fields
    # ---------------------------------
    
    # accountStatus = models.CharField(
    #     max_length=20,
    #     choices=AccountStatus.choices
    # )
    
    is_claimed = models.BooleanField(
        default=False,
        help_text=_("Indicates whether the user has claimed their account"),
    )
    
    # This field is used for claim-based verification
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text=_("Used for identity verification during claim flow"),
    )
    
    # ---------------------------
    # Django Auth Configuration
    # ---------------------------
    
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "date_of_birth"]
    
    objects = UserManager()
    
    # ---------------------------
    # Model Validation
    # ---------------------------
    
    def clean(self):
        """
        Enforce role-based constraints.
        
        Ensures:
        - Students MUST have student_id
        - Staff/Admin MUST have staff_id or email
        """
        
        if self.role == self.UserType.STUDENT:
            if not self.student_id:
                raise ValidationError(_("Students must have a student ID"))
            
        if self.role in [self.UserType.STAFF, self.UserType.ADMIN]:
            if not (self.staff_id or self.email):
                raise ValidationError(_("Staff/Admin must have a staff id or an email"))
        
        
    # -----------------------------
    # Utility Methods
    # -----------------------------
    
    def __str__(self):
        """
        Human-readable representation of the user.

        Helps with admin panel, logs, and debugging.
        """
        if self.role == self.UserType.STUDENT:
            return f"Student ({self.student_id})"
        if self.role == self.UserType.STAFF:
            return f"Staff {self.staff_id} ({self.email})"
        
        return f"Admin {self.staff_id} ({self.email})"
    
    # Return True or False for the user role 
    @property
    def is_student(self):
        return self.role == self.UserType.STUDENT
    @property
    def is_staff_member(self):
        return self.role == self.UserType.STAFF
    @property
    def is_admin_user(self):
        return self.role == self.UserType.ADMIN
    
    @property
    def primary_identifier(self):
        """
        Returns the main identifier for display/logging purpose.
        """
        return self.student_id or self.staff_id or self.email or self.username
    
    def save(self, *args, **kwargs):
        # Enforce validation before saving
        self.full_clean()
        super().save(*args, **kwargs)