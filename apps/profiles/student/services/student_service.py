from typing import Any
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.student.models.student_models import Student

# Database locking
from apps.core.db.locking import get_locked_instance

# POLICIES
from apps.core.policies import StudentPolicy

# Application Exceptions
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    NotFoundError,
    PermissionDenied,
)


class StudentService:
    """
    Service layer to handle business logic and mutations
    for user with Student profile.
    """

    @staticmethod
    def _get_locked_student(student: Student) -> Student:
        """Reload the profile under the same row lock used by allocation."""
        try:
            return get_locked_instance(Student, student.pk, mode="exclusive")
        except Student.DoesNotExist as exc:
            raise NotFoundError("The requested student could not be found.") from exc

    @staticmethod
    def _is_housing_eligible(student: Student) -> bool:
        """Check the admission and housing statuses required for accommodation."""
        return (
            student.admission_status == Student.AdmissionStatus.ACCEPTED
            and student.eligibility_status == Student.EligibilityStatus.ELIGIBLE
        )

    @staticmethod
    def _save_housing_status(student: Student, *, field: str, value: str) -> Student:
        """Save a status change and flag assignments when eligibility is lost.

        The caller holds the exclusive Student lock inside its transaction.
        The same transaction saves the new profile status and opens the
        assignment review, so both changes roll back if either one fails.
        """
        was_eligible = StudentService._is_housing_eligible(student)

        setattr(student, field, value)
        student.full_clean()
        student.save(update_fields=[field])

        # Repeated saves of an ineligible status should not reopen a review
        # that the building manager has already decided.
        if was_eligible and not StudentService._is_housing_eligible(student):
            from apps.assignments.services.assignment_service import AssignmentService

            AssignmentService.flag_eligibility_review(student=student)

        return student
    
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
            
        student = StudentService._get_locked_student(student)

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

        return StudentService._save_housing_status(
            student, field="admission_status", value=Student.AdmissionStatus.ACCEPTED,
        )

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

        student = StudentService._get_locked_student(student)
        
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

        return StudentService._save_housing_status(
            student, field="admission_status", value=Student.AdmissionStatus.REJECTED,
        )

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
        
        student = StudentService._get_locked_student(student)

        if student.admission_status == Student.AdmissionStatus.REJECTED:
            raise ConflictError(
                "A rejected student cannot be withdrawn."
            )

        return StudentService._save_housing_status(
            student, field="admission_status", value=Student.AdmissionStatus.WITHDRAWN,
        )

    @staticmethod
    @transaction.atomic
    def set_eligibility(
        *, 
        actor: Any,
        student: Student, 
        eligibility_status: str
    ) -> Student:
        """Update the student's accommodation eligibility status."""
        student = StudentService._get_locked_student(student)

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

        return StudentService._save_housing_status(
            student, field="eligibility_status", value=eligibility_status,
        )

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
        user.accountStatus = "ACTIVE"

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
        user.accountStatus = "LOCKED"

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
        user.accountStatus = "SUSPENDED"

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
            
        if student.user.accountStatus != "SUSPENDED":
            raise ConflictError(
                "Only suspended student accounts can be restored."
            )

        user = student.user

        user.is_active = True
        user.accountStatus = "ACTIVE"

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
