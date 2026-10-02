from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.profiles.student.models.campus_assignment import StudentAssignCampus
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
)


class CampusAssignmentService:

    @staticmethod
    @transaction.atomic
    def assign_student(
        *,
        student,
        campus,
        academic_year,
        start_date,
        campus_arrival_date,
        reason="",
    ):

        existing = (
            StudentAssignCampus.objects
            .for_student(student)
            .for_academic_year(academic_year)
            .active()
            .first()
        )

        if existing:
            raise ConflictError(
                "Student already has an active campus assignment "
                "for this academic year."
            )

        assignment = StudentAssignCampus(
            student=student,
            campus=campus,
            academic_year=academic_year,
            start_date=start_date,
            campus_arrival_date=campus_arrival_date,
            status=StudentAssignCampus.AssignmentStatus.ACTIVE,
            reason=reason,
        )

        try:
            assignment.full_clean()
            assignment.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return assignment

    @staticmethod
    @transaction.atomic
    def transfer_student(
        *,
        student,
        new_campus,
        academic_year,
        start_date,
        campus_arrival_date,
        reason="",
    ):

        current = (
            StudentAssignCampus.objects
            .for_student(student)
            .for_academic_year(academic_year)
            .active()
            .select_for_update()
            .first()
        )

        if not current:
            raise ConflictError(
                "Student does not have an active campus assignment."
            )

        if current.campus_id == new_campus.pk:
            raise ConflictError(
                "Student is already assigned to this campus."
            )

        current.status = (
            StudentAssignCampus.AssignmentStatus.TRANSFERRED
        )
        current.end_date = start_date

        current.full_clean()
        current.save(
            update_fields=[
                "status",
                "end_date",
            ]
        )

        new_assignment = StudentAssignCampus(
            student=student,
            campus=new_campus,
            academic_year=academic_year,
            start_date=start_date,
            campus_arrival_date=campus_arrival_date,
            status=StudentAssignCampus.AssignmentStatus.ACTIVE,
            reason=reason,
        )

        try:
            new_assignment.full_clean()
            new_assignment.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)

        return new_assignment

    @staticmethod
    @transaction.atomic
    def end_assignment(
        *,
        assignment,
        end_date,
    ):
        if assignment.status != (
            StudentAssignCampus.AssignmentStatus.ACTIVE
        ):
            raise ConflictError(
                "Only active campus assignments can be ended."
            )

        if end_date <= assignment.start_date:
            raise ValidationError(
                "Assignment end date must be after start date."
            )

        assignment.status = (
            StudentAssignCampus.AssignmentStatus.ENDED
        )
        assignment.end_date = end_date

        assignment.full_clean()
        assignment.save(
            update_fields=[
                "status",
                "end_date",
            ]
        )

        return assignment