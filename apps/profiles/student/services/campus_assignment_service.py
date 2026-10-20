from typing import Any
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# MODELS
from apps.profiles.student.models.campus_assignment import StudentAssignCampus

# POLICIES
from apps.core.policies import AcademicPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ValidationError,
    ConflictError,
    PermissionDenied,
)


class CampusAssignmentService:

    @staticmethod
    @transaction.atomic
    def assign_student(
        *,
        actor: Any,
        student: Any,
        campus: Any,
        academic_year: str,
        start_date: Any,
        campus_arrival_date: Any,
        reason: str="",
    ) -> StudentAssignCampus:
        """
        Assign a student to a campus for a specific academic 
        year.
        
        Raises:
            ConflictError: If the student already has an
                           active assignment.
            ValidationError: If model field validation fails.
        """
        if not AcademicPolicy.can_create_campus_assignment(
            actor
        ):
            raise PermissionDenied(
                "This action is reserve for admin"
            )
            
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
        actor,
        student,
        new_campus,
        academic_year,
        start_date,
        campus_arrival_date,
        reason="",
    ):
        """
        Transfers a student from their current campus to a
        new campus.
        Uses select_for_related() to prevent concurrent
        modification race conditions.
        
        Raises:
            ConflictError: If student has no active assignment
                           or is already on the target campus
            ValidationError: If model field validation fails 
        """
        if not AcademicPolicy.can_transfer_campus_assignment(
            actor,
        ):
            raise PermissionDenied(
                "This action is reserve for admin"
            )
        
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
        actor,
        assignment,
        end_date,
        reason=None,
    ):
        """
        Ends an active campus assignment.
        
        Raises:
            ConflictError: If the assignment is not currently
                           active.
            ValidationError: If the end date is before or
                             equal to the start date.
        """
        if not AcademicPolicy.can_end_campus_assignment(
            actor,
        ):
            raise PermissionDenied(
                "This action is reserved for admin"
            )
            
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
        
        if reason is not None:
            assignment.reason = reason.strip()

        assignment.full_clean()
        assignment.save(
            update_fields=[
                "status",
                "end_date",
                "reason",
            ]
        )

        return assignment