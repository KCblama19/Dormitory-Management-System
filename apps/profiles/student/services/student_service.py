from typing import Any
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.student.models.student_models import Student

# POLICIES
from apps.core.policies import StudentPolicy

# Application Exceptions
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    PermissionDenied,
)


class StudentService:
    """
    Service layer to handle business logic and mutations
    for user with Student profile.
    """
    
    @staticmethod
    @transaction.atomic
    def create_student(
        *,
        actor: Any,
        user: Any,
        student_id: str,
        first_name: str,
        middle_name: str ="",
        last_name: str,
        gender: str,
        nationality: Any,
        admission_status: str = Student.AdmissionStatus.PENDING,
        eligibility_status: str = Student.EligibilityStatus.PENDING,
        bio: str ="",
    ) -> Student:
        """
        Creates a new student profiles linked to a user
        account.
        
        Raises:
            PermissionDenied: if actor lacks creation rights
            ConflictError: If student_id already exists or
                           user already has a profile.
            ValidationError: If user account type is invalid
                             or model validation fails

        """
        
        if not StudentPolicy.can_create_student(actor):
            raise PermissionDenied(
                "You do not have permission to create students."
            )
            
        if Student.objects.filter(
            student_id=student_id
        ).exists():
            raise ConflictError(
                f"Student ID '{student_id}' already exists."
            )

        if hasattr(user, "student"):
            raise ConflictError(
                "This user already has a student profile."
            )

        if not user.is_student:
            raise ValidationError(
                "The user account must have STUDENT account type."
            )

        student = Student(
            user=user,
            student_id=str(student_id).strip(),
            first_name=first_name.strip(),
            middle_name=middle_name.strip(),
            last_name=last_name.strip(),
            gender=gender,
            nationality=nationality,
            admission_status=admission_status,
            eligibility_status=eligibility_status,
            bio=bio.strip(),
        )

        try:
            student.full_clean()
            student.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return student

    @staticmethod
    @transaction.atomic
    def accept_student(
        *, 
        actor: Any, 
        student: Student
    ) -> Student:
        """
        Approves/accepts a pending student application
        """
        
        if not StudentPolicy.can_accept_student(
            actor,
        ):
            raise PermissionDenied(
                "You do not have permission to accept "
                "this student."
            )
            
        if student.admission_status == Student.AdmissionStatus.ACCEPTED:
            raise ConflictError(
                "Student has already been accepted."
            )

        if student.admission_status in {
            Student.AdmissionStatus.REJECTED,
            Student.AdmissionStatus.WITHDRAWN,
        }:
            raise ConflictError(
                "A rejected or withdrawn student cannot be directly accepted."
            )

        student.admission_status = Student.AdmissionStatus.ACCEPTED
        student.full_clean()
        student.save(update_fields=["admission_status"])

        return student

    @staticmethod
    @transaction.atomic
    def reject_student(
        *, 
        actor: Any, 
        student: Student
        ) -> Student:
        """
        Rejects a student application.
        """
        
        if not StudentPolicy.can_reject_student(
            actor, student,
        ):
            raise PermissionDenied(
                "You do not have the permission to "
                "reject this student."
            )
            
        if student.admission_status == Student.AdmissionStatus.ACCEPTED:
            raise ConflictError(
                "An accepted student cannot be rejected directly."
            )

        student.admission_status = Student.AdmissionStatus.REJECTED
        student.full_clean()
        student.save(update_fields=["admission_status"])

        return student

    @staticmethod
    @transaction.atomic
    def withdraw_student(
        *, 
        actor: Any, 
        student: Student
    ) -> Student:
        """
        Marks a student application as withdrawn
        """
        if not StudentPolicy.can_withdraw_student(
            actor,
        ):
            raise PermissionDenied(
                "You do not have the permission to "
                "withdraw this student"
            )
        
        if student.admission_status == Student.AdmissionStatus.REJECTED:
            raise ConflictError(
                "A rejected student cannot be withdrawn."
            )

        student.admission_status = Student.AdmissionStatus.WITHDRAWN
        student.full_clean()
        student.save(update_fields=["admission_status"])

        return student

    @staticmethod
    @transaction.atomic
    def set_eligibility(
        *, 
        actor: str, 
        student: Student, 
        eligibility_status: str
    ) -> Student:
        """"
        Updates a student's accommodation eligibility status
        """
        if not StudentPolicy.can_set_eligibility(
            actor,
            student,
        ):
            raise PermissionDenied(
                "You do not have permission to change this "
                "student's eligibility."
            )
            
        valid_statuses = {
            value
            for value, _ in Student.EligibilityStatus.choices
        }

        if eligibility_status not in valid_statuses:
            raise ValidationError(
                f"Invalid eligibility status: {eligibility_status}"
            )

        student.eligibility_status = eligibility_status
        student.full_clean()
        student.save(update_fields=["eligibility_status"])

        return student

    @staticmethod
    @transaction.atomic
    def activate_account(*, actor:Any, student: Student) -> Student:
        """
        Activates a student's underlying user account.
        """
        if not StudentPolicy.can_activate_student_account(
            actor,
            student,
        ):
            raise PermissionDenied(
                "You do not have permission to activate this "
                "student's account"
            )
            
        user = student.user

        user.is_active = True
        user.accountStatus = "active"

        user.full_clean()
        user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )

        return student

    @staticmethod
    @transaction.atomic
    def deactivate_account(*, actor: Any, student: Student) -> Student:
        """
        Deactivates and locks a student's underlying user
        account.
        """
        
        if not StudentPolicy.can_deactivate_student_account(
            actor,
            student,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate "
                "this student's account."
            )
        
        user = student.user

        user.is_active = False
        user.accountStatus = "locked"

        user.full_clean()
        user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )

        return student

    @staticmethod
    @transaction.atomic
    def suspend_account(*, actor, student):
        """
        Suspends a student's underlying user account.
        """
        
        if not StudentPolicy.can_suspend_student_account(
            actor,
            student,
        ):
            raise PermissionDenied(
                "You do not have permission to suspend "
                "this student's account."
            )
            
        user = student.user

        user.is_active = False
        user.accountStatus = "suspended"

        user.full_clean()
        user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )

        return student

    @staticmethod
    @transaction.atomic
    def restore_account(*, actor: Any, student: Student) -> Student:
        """
        Restores a suspended student account back to active
        status.
        """
        
        if not StudentPolicy.can_restore_student_account(
            actor,
            student,
        ):
            raise PermissionDenied(
                "You do not have the permission to restore "
                "this student's account."
            )
            
        if student.user.accountStatus != "suspended":
            raise ConflictError(
                "Only suspended student accounts can be restored."
            )

        user = student.user

        user.is_active = True
        user.accountStatus = "active"

        user.full_clean()
        user.save(
            update_fields=[
                "is_active",
                "accountStatus",
            ]
        )


        return student

    @staticmethod
    def get_ready_for_accommodation(*, student_id: str) -> Student:
        """"
        Retrieves a student record if they are fully cleared
        and ready for room assignment.
        """
        return (
            Student.objects
            .ready_for_accommodation()
            .filter(pk=student_id)
            .first()
        )