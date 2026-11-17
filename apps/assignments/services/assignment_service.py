from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# DJANGO EXCEPTIONS
from django.core.exceptions import (
    ImproperlyConfigured,
    ObjectDoesNotExist,
    ValidationError as DjangoValidationError,
)

# TimeZone and db
from django.db import IntegrityError, transaction
from django.utils import timezone

# MODELS IMPORT
from apps.accommodations.models import Bed, Floor
from apps.assignments.models import Assignment

# CORE AND APPLICATION EXCEPTIONS
from apps.core.db.locking import lock_instance
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)

# POLICIES
from apps.assignments.policies.assignment_policy import AssignmentPolicy


def _campus_local_date(campus, instant):
    """Convert an aware timestamp to the university's calendar date."""
    zone_name = getattr(campus, "timezone", None)

    if not isinstance(zone_name, str) or not zone_name.strip():
        raise ImproperlyConfigured(
            f"{campus.name} must have a configured IANA timezone."
        )

    try:
        campus_zone = ZoneInfo(zone_name.strip())
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ImproperlyConfigured(
            f"{campus.name} Campus timezone {zone_name!r} is invalid."
        ) from exc

    return timezone.localdate(instant, campus_zone)


def _last_check_in_date(assignment):
    """Return the last calendar date on which check-in is permitted."""
    return assignment.check_in_deadline + timedelta(
        days=assignment.grace_period_days,
    )


class AssignmentService:
    """Manage the reservation lifecycle for allocation-origin assignments."""

    @staticmethod
    def _get_locked_assignment(assignment_id):
        """
        Lock the student, accommodation hierarchy, and assignment in order.

        The initial read identifies the rows to lock. The second read
        supplies the current state for authorization and validation.
        """
        assignments = Assignment.objects.select_related(
            "student",
            "bed__room__floor__building__campus__university",
        )

        def lock_path(assignment):
            bed = assignment.bed
            room = bed.room
            floor = room.floor
            building = floor.building
            campus = building.campus

            return (
                assignment.student,
                campus.university,
                campus,
                building,
                floor,
                room,
                bed,
            )

        try:
            reference = assignments.get(pk=assignment_id)
            resources = lock_path(reference)

            # The accommodation services take exclusive locks when
            # changing these resources. Check-in only reads their state.
            for resource in resources:
                lock_instance(resource, mode="shared")

            lock_instance(reference, mode="exclusive")
            assignment = assignments.get(pk=assignment_id)
        except ObjectDoesNotExist as exc:
            raise NotFoundError(
                "The assignment or its accommodation could not be found."
            ) from exc

        if lock_path(assignment) != resources:
            raise ConflictError(
                "The assignment's student or accommodation changed. Please retry."
            )

        return assignment

    @staticmethod
    def _require_allocation_reservation(assignment):
        if assignment.status != Assignment.Status.RESERVED:
            raise ConflictError("The assignment must be reserved.")

        if assignment.transfer_request_id is not None:
            raise ConflictError(
                "Complete or cancel this reservation through its transfer request."
            )

    @staticmethod
    def _save_assignment(assignment, *, fields):
        try:
            with transaction.atomic():
                assignment.full_clean()
                assignment.save(update_fields=[*fields, "updated_at"])
        except DjangoValidationError as exc:
            raise ValidationError(" ".join(exc.messages)) from exc
        except IntegrityError as exc:
            raise ConflictError(
                "The assignment transition conflicts with an existing record."
            ) from exc

        return assignment

    @classmethod
    @transaction.atomic
    def cancel_reservation(cls, *, actor, assignment, reason):
        """Cancel a reservation and record who cancelled it and why."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_cancel_reservation(actor, assignment):
            raise PermissionDenied(
                "You do not have permission to cancel this reservation."
            )

        cls._require_allocation_reservation(assignment)

        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A cancellation reason is required.")

        assignment.status = Assignment.Status.CANCELLED
        assignment.cancelled_at = timezone.now()
        assignment.cancelled_by = actor
        assignment.cancellation_reason = reason.strip()

        return cls._save_assignment(
            assignment,
            fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
            ],
        )

    @classmethod
    @transaction.atomic
    def check_in(cls, *, actor, assignment, approve_early=False):
        """Check in a student, recording explicit early approval when needed."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_check_in(actor, assignment):
            raise PermissionDenied(
                "You do not have permission to check in this student."
            )

        cls._require_allocation_reservation(assignment)

        bed = assignment.bed
        floor = bed.room.floor
        building = floor.building
        campus = building.campus
        university = campus.university

        # Take the timestamp after locking. A call that waited across
        # midnight must use the new campus-local date.
        now = timezone.now()
        local_date = _campus_local_date(campus, now)

        if local_date > _last_check_in_date(assignment):
            raise ConflictError("The check-in deadline and grace period have passed.")

        is_early = local_date < assignment.expected_check_in

        if is_early:
            if approve_early is not True:
                raise ValidationError("Early check-in requires explicit approval.")

            if not AssignmentPolicy.can_approve_early_check_in(actor, assignment):
                raise PermissionDenied(
                    "You do not have permission to approve early check-in."
                )

        if (
            not university.is_active
            or not campus.is_active
            or not building.is_active
            or not floor.is_active
            or floor.status != Floor.FloorStatus.ACTIVE
            or bed.status != Bed.Status.AVAILABLE
        ):
            raise ConflictError("The assigned bed is unavailable for check-in.")

        student = assignment.student

        if (
            student.admission_status != student.AdmissionStatus.ACCEPTED
            or student.eligibility_status != student.EligibilityStatus.ELIGIBLE
            or assignment.review_status in {"PENDING", "REJECTED"}
        ):
            raise ConflictError(
                "The student must be eligible and clear of pending or rejected "
                "eligibility reviews before check-in."
            )

        assignment.status = Assignment.Status.CHECKED_IN
        assignment.actual_check_in = now
        assignment.early_check_in_approved_by = actor if is_early else None

        return cls._save_assignment(
            assignment,
            fields=["status", "actual_check_in", "early_check_in_approved_by"],
        )