from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.profiles.student.models.enrollment import StudentEnrollment
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
)


class EnrollmentService:

    @staticmethod
    @transaction.atomic
    def create_enrollment(
        *,
        student,
        program,
        academic_year,
        start_date,
        end_date=None,
        expected_graduation_date=None,
        year_of_study=None,
        is_primary=True,
        enrollment_status=StudentEnrollment.EnrollmentStatus.ACTIVE,
    ):

        existing_active = (
            StudentEnrollment.objects
            .for_student(student)
            .for_academic_year(academic_year)
            .active()
        )

        if is_primary and existing_active.primary().exists():
            raise ConflictError(
                "The student already has a primary active enrollment "
                "for this academic year."
            )

        enrollment = StudentEnrollment(
            student=student,
            program=program,
            academic_year=academic_year,
            start_date=start_date,
            end_date=end_date,
            expected_graduation_date=expected_graduation_date,
            year_of_study=year_of_study,
            is_primary=is_primary,
            enrollment_status=enrollment_status,
        )

        try:
            enrollment.full_clean()
            enrollment.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return enrollment

    @staticmethod
    @transaction.atomic
    def activate_enrollment(*, enrollment):

        if enrollment.enrollment_status == (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        ):
            raise ConflictError(
                "Enrollment is already active."
            )

        enrollment.enrollment_status = (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        )

        enrollment.full_clean()
        enrollment.save(
            update_fields=["enrollment_status"]
        )

        return enrollment

    @staticmethod
    @transaction.atomic
    def complete_enrollment(
        *,
        enrollment,
        end_date,
    ):
        if enrollment.enrollment_status != (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        ):
            raise ConflictError(
                "Only active enrollments can be completed."
            )

        if end_date <= enrollment.start_date:
            raise ValidationError(
                "Enrollment end date must be after start date."
            )

        enrollment.enrollment_status = (
            StudentEnrollment.EnrollmentStatus.COMPLETED
        )
        enrollment.end_date = end_date
        enrollment.is_primary = False

        enrollment.full_clean()
        enrollment.save(
            update_fields=[
                "enrollment_status",
                "end_date",
                "is_primary",
            ]
        )

        return enrollment

    @staticmethod
    @transaction.atomic
    def withdraw_enrollment(
        *,
        enrollment,
        end_date,
    ):
        if enrollment.enrollment_status in {
            StudentEnrollment.EnrollmentStatus.COMPLETED,
            StudentEnrollment.EnrollmentStatus.WITHDRAWN,
        }:
            raise ConflictError(
                "This enrollment is already closed."
            )

        if end_date <= enrollment.start_date:
            raise ValidationError(
                "Enrollment end date must be after start date."
            )

        enrollment.enrollment_status = (
            StudentEnrollment.EnrollmentStatus.WITHDRAWN
        )
        enrollment.end_date = end_date
        enrollment.is_primary = False

        enrollment.full_clean()
        enrollment.save(
            update_fields=[
                "enrollment_status",
                "end_date",
                "is_primary",
            ]
        )

        return enrollment

    @staticmethod
    @transaction.atomic
    def suspend_enrollment(*, enrollment):

        if enrollment.enrollment_status != (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        ):
            raise ConflictError(
                "Only active enrollments can be suspended."
            )

        enrollment.enrollment_status = (
            StudentEnrollment.EnrollmentStatus.SUSPENDED
        )

        enrollment.full_clean()
        enrollment.save(
            update_fields=["enrollment_status"]
        )

        return enrollment

    @staticmethod
    @transaction.atomic
    def defer_enrollment(*, enrollment):

        if enrollment.enrollment_status != (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        ):
            raise ConflictError(
                "Only active enrollments can be deferred."
            )

        enrollment.enrollment_status = (
            StudentEnrollment.EnrollmentStatus.DEFERRED
        )

        enrollment.full_clean()
        enrollment.save(
            update_fields=["enrollment_status"]
        )

        return enrollment

    @staticmethod
    @transaction.atomic
    def set_primary_enrollment(*, enrollment):

        if enrollment.enrollment_status != (
            StudentEnrollment.EnrollmentStatus.ACTIVE
        ):
            raise ValidationError(
                "Only active enrollments can be primary."
            )

        (
            StudentEnrollment.objects
            .for_student(enrollment.student)
            .for_academic_year(enrollment.academic_year)
            .primary_active()
            .exclude(pk=enrollment.pk)
            .update(is_primary=False)
        )

        enrollment.is_primary = True
        enrollment.full_clean()
        enrollment.save(update_fields=["is_primary"])

        return enrollment