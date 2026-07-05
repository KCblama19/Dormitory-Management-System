from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _
from accounts.utils.identity import generate_internal_username
import uuid


class UserManager(BaseUserManager):
    
    """
    Custom user manager that handles three distinct user types:

    - Students → authenticate using student ID (via custom backend later)
    - Staff → authenticate using email or staff ID
    - Admins (Superusers) → authenticate using email or staff ID
    
    Responsibilities:
    - Create students (bulk/import)
    - Create staff/admin users
    - Enforce correct defaults of each user types

    The system uses the `username` field internally as a stable identifier.
    """

    # -----------------------------------
    # BASE USER CREATION (REQUIRED BY DJANGO)
    # -----------------------------------
    def create_user(self, username=None, password=None, **extra_fields):
        """
        Normal user creation.
        """

        if not username:
            username = generate_internal_username()
        
        user = self.model(
            username=username, 
            **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.full_clean()
        user.save(using=self._db)
        return user
    
    # -----------------------------------
    # STUDENT CREATION
    # -----------------------------------
    def create_student(self, student_id, email=None, **extra_fields):
        """
        Create and save a Student user.

        Key design decisions:
        - Student logs in using student_id (via custom backend later)
        - Account is inactive by default (activation required)
        - No password is set initially (user must set via activation link)
        """

        if not student_id:
            raise ValueError(_("Student ID is required"))

        if email:
            email = self.normalize_email(email)
            

        if extra_fields.get("role") in [self.model.UserType.ADMIN, self.model.UserType.STAFF]:
            raise ValueError(_("Use create_staff or create_superuser"))

        extra_fields.setdefault("role", self.model.UserType.STUDENT)
        extra_fields.setdefault("is_claimed", False)
        extra_fields.setdefault("is_active", True)
        
        """
        create a unique identifier 
        based on the user role
        ie: "Student_2g01h"
        """
        username = generate_internal_username(self.model.UserType.STUDENT)
        student_id = str(student_id).strip()
        date_of_birth = extra_fields.get("date_of_birth")
        if not date_of_birth:
            raise ValueError(_("Date of birth is required for claim flow"))

        user = self.create_user(
            username=username, 
            student_id=student_id,
            email=email,
            date_of_birth=date_of_birth,
            **extra_fields,
        )

        return user
    
    # -----------------------------------
    # STAFF CREATION
    # -----------------------------------
    def create_staff(self, staff_id, email=None, **extra_fields):
        """
        Create and save a Staff user.
        """
        
        if not staff_id:
            raise ValueError(_("Staff ID is required"))
        

        if extra_fields.get("role") == self.model.UserType.STUDENT:
            raise ValueError(_("Use create_student for student creation"))
        if extra_fields.get("role") == self.model.UserType.ADMIN:
            raise ValueError(_("Use create_superuser for admin creation"))
        
        """
        create a unique identifier 
        based on the user role
        ie: "Staff_2g01h"
        """
        username = generate_internal_username(self.model.UserType.STAFF) # create a unique identifier 
        email = self.normalize_email(email)
        staff_id = str(staff_id).strip()
        date_of_birth = extra_fields.get("date_of_birth")
        if not date_of_birth:
            raise ValueError(_("Date of birth is required for claim flow"))

        extra_fields.setdefault("role", self.model.UserType.STAFF)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        user = self.create_user(
            username=username,
            staff_id=staff_id,
            email=email,
            date_of_birth=date_of_birth,
            **extra_fields,
        )

        return user
    
    # -----------------------------------
    # SUPERUSER CREATION
    # -----------------------------------
    def create_superuser(self, username, password=None, email=None, staff_id=None, **extra_fields):
        """
        Create and save a Superuser (Admin).

        Compatible with Django's createsuperuser command.
        """

        if not password:
            raise ValueError(_("Password is required"))

        extra_fields["role"] = self.model.UserType.ADMIN
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields["is_active"] = True
        extra_fields["is_claimed"] = True
        
        """
        create a unique identifier 
        based on the user role
        ie: "Admin_2g01h"
        """
        username = username or generate_internal_username(self.model.UserType.ADMIN) 
        
        email = self.normalize_email(email) if email else None
        
        if not email and not staff_id:
            raise ValueError("Admin must provide email or staff_id")            

        user = self.create_user(
            username=username,
            password=password,
            staff_id=staff_id,
            email=email,
            **extra_fields,
        )

        return user