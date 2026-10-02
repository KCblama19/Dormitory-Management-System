from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.student.models.student_models import Student

# Application Exceptions
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    NotFoundError,
    PermissionDenied,
)


class StudentService:

    @staticmethod
    @transaction.atomic
    def create_student(
        *,
        user,
        student_id,
        first_name,
        last_name,
        gender,
        nationality,
        middle_name="",
        admission_status=Student.AdmissionStatus.PENDING,
        eligibility_status=Student.EligibilityStatus.PENDING,
        bio="",
    ):
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
    def accept_student(*, student):
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
    def reject_student(*, student):
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
    def withdraw_student(*, student):
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
    def set_eligibility(*, student, eligibility_status):
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
    def activate_account(*, student):
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
    def deactivate_account(*, student):
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
    def suspend_account(*, student):
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
    def restore_account(*, student):
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
    def get_ready_for_accommodation(*, student_id):
        return (
            Student.objects
            .ready_for_accommodation()
            .filter(pk=student_id)
            .first()
        )