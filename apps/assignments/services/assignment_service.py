from datetime import timedelta, date, datetime
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
from apps.assignments.models import (
    Assignment, 
    AssignmentExtension,
    CheckoutRequest,
    TransferRequest
)

# CORE AND APPLICATION EXCEPTIONS
from apps.core.db.locking import lock_instance, get_locked_instance
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)

# POLICIES
from dorm_system.apps.core.policies.assignment_policy import AssignmentPolicy


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
        
    @classmethod
    @transaction.atomic
    def process_reservation_deadline(cls, *, assignment_id):
        """Apply one overdue or expiration transition for the scheduler."""
        assignment = cls._get_locked_assignment(assignment_id)

        if (
            assignment.status != Assignment.Status.RESERVED
            or assignment.transfer_request_id is not None
        ):
            return None

        # Check the clock and deadline after locking. A check-in or
        # extension approval may have completed while this call waited.
        now = timezone.now()
        campus = assignment.bed.room.floor.building.campus
        local_date = _campus_local_date(campus, now)

        if local_date > _last_check_in_date(assignment):
            assignment.status = Assignment.Status.EXPIRED
            assignment.expired_at = now
            cls._save_assignment(
                assignment,
                fields=["status", "expired_at"],
            )
            return "expired"

        if (
            local_date > assignment.check_in_deadline
            and assignment.overdue_at is None
        ):
            assignment.overdue_at = now
            cls._save_assignment(assignment, fields=["overdue_at"])
            return "overdue"

        return None
    
    @classmethod
    def _get_extension_local_date(cls, assignment, now):
        """Return the local date while the reservation can still be extended."""
        cls._require_allocation_reservation(assignment)

        campus = assignment.bed.room.floor.building.campus
        local_date = _campus_local_date(campus, now)

        if local_date > _last_check_in_date(assignment):
            raise ConflictError(
                "The reservation's check-in deadline and grace period have passed."
            )

        return local_date

    @staticmethod
    def _save_workflow_request(request, *, update_fields=None):
        try:
            with transaction.atomic():
                request.full_clean()
                if update_fields is None:
                    request.save(force_insert=True)
                else:
                    request.save(update_fields=[*update_fields, "updated_at"])
        except DjangoValidationError as exc:
            raise ValidationError(" ".join(exc.messages)) from exc
        except IntegrityError as exc:
            raise ConflictError(
                "The request conflicts with an existing record."
            ) from exc

        return request

    @classmethod
    @transaction.atomic
    def request_extension(
        cls,
        *,
        actor,
        assignment,
        requested_check_in_deadline,
        reason="",
    ):
        """Request a later check-in deadline for the student's reservation."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_request_extension(actor, assignment):
            raise PermissionDenied(
                "You can only request an extension for your own assignment."
            )

        cls._get_extension_local_date(assignment, timezone.now())

        if (
            not isinstance(requested_check_in_deadline, date)
            or isinstance(requested_check_in_deadline, datetime)
        ):
            raise ValidationError("Supply a calendar date for the requested deadline.")

        if requested_check_in_deadline <= assignment.check_in_deadline:
            raise ValidationError(
                "The requested deadline must be later than the current deadline."
            )

        if not isinstance(reason, str):
            raise ValidationError("The extension reason must be text.")

        if assignment.extensions.filter(
            status=AssignmentExtension.Status.PENDING,
        ).exists():
            raise ConflictError("This assignment already has a pending extension.")

        return cls._save_workflow_request(
            AssignmentExtension(
                assignment=assignment,
                requested_check_in_deadline=requested_check_in_deadline,
                reason=reason.strip(),
            )
        )

    @classmethod
    @transaction.atomic
    def decide_extension(cls, *, actor, extension, approve, decision_note=""):
        """Approve or reject a pending extension and record the decision."""
        try:
            assignment_id = AssignmentExtension.objects.values_list(
                "assignment_id",
                flat=True,
            ).get(pk=extension.pk)

            # Lock the assignment first so this decision serializes with
            # check-in, cancellation, and the no-show expiration command.
            assignment = cls._get_locked_assignment(assignment_id)
            extension = get_locked_instance(
                AssignmentExtension,
                extension.pk,
                mode="exclusive",
            )
        except AssignmentExtension.DoesNotExist as exc:
            raise NotFoundError("The extension request could not be found.") from exc

        if extension.assignment_id != assignment.pk:
            raise ConflictError(
                "The extension's assignment changed. Please retry."
            )

        extension.assignment = assignment

        if not AssignmentPolicy.can_decide_extension(actor, extension):
            raise PermissionDenied(
                "You do not have permission to decide this extension."
            )

        if extension.status != AssignmentExtension.Status.PENDING:
            raise ConflictError("This extension has already been decided.")

        if not isinstance(approve, bool):
            raise ValidationError("The decision must specify approval or rejection.")

        if not isinstance(decision_note, str):
            raise ValidationError("The decision note must be text.")

        now = timezone.now()

        if approve:
            local_date = cls._get_extension_local_date(assignment, now)
            requested_deadline = extension.requested_check_in_deadline

            if requested_deadline <= assignment.check_in_deadline:
                raise ConflictError(
                    "The requested deadline is no longer later than "
                    "the assignment's current deadline."
                )

            assignment.check_in_deadline = requested_deadline
            fields = ["check_in_deadline"]

            # A deadline on or after today brings the reservation out
            # of overdue status. It can become overdue again later.
            if local_date <= requested_deadline and assignment.overdue_at is not None:
                assignment.overdue_at = None
                fields.append("overdue_at")

            cls._save_assignment(assignment, fields=fields)
            extension.status = AssignmentExtension.Status.APPROVED
        else:
            extension.status = AssignmentExtension.Status.REJECTED

        extension.decided_by = actor
        extension.decided_at = now
        extension.decision_note = decision_note.strip()

        return cls._save_workflow_request(
            extension,
            update_fields=["status", "decided_by", "decided_at", "decision_note"],
        )
        
    @classmethod
    @transaction.atomic
    def request_checkout(
        cls,
        *,
        actor,
        assignment,
        requested_checkout_date,
        reason="",
    ):
        """Submit a checkout request for the student's occupied assignment."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_request_checkout(actor, assignment):
            raise PermissionDenied(
                "You can only request checkout for your own assignment."
            )

        if assignment.status != Assignment.Status.CHECKED_IN:
            raise ConflictError("Checkout requires a checked-in assignment.")

        if (
            not isinstance(requested_checkout_date, date)
            or isinstance(requested_checkout_date, datetime)
        ):
            raise ValidationError("Supply a calendar date for the requested checkout.")

        if not isinstance(reason, str):
            raise ValidationError("The checkout reason must be text.")

        if assignment.checkout_requests.filter(
            status=CheckoutRequest.Status.PENDING,
        ).exists():
            raise ConflictError("This assignment already has a pending checkout request.")

        return cls._save_workflow_request(
            CheckoutRequest(
                assignment=assignment,
                requested_checkout_date=requested_checkout_date,
                reason=reason.strip(),
            )
        )

    @classmethod
    @transaction.atomic
    def resolve_checkout_request(
        cls,
        *,
        actor,
        checkout_request,
        approve,
        departure_confirmed=False,
        decision_note="",
    ):
        """Resolve a checkout request and release the bed on approval."""
        request_id = checkout_request.pk

        try:
            assignment_id = CheckoutRequest.objects.values_list(
                "assignment_id",
                flat=True,
            ).get(pk=request_id)

            # Lock the assignment first so the decision uses fresh
            # occupancy state and shares the transfer workflow's lock order.
            assignment = cls._get_locked_assignment(assignment_id)
            checkout_request = get_locked_instance(
                CheckoutRequest,
                request_id,
                mode="exclusive",
            )
        except CheckoutRequest.DoesNotExist as exc:
            raise NotFoundError("The checkout request could not be found.") from exc

        if checkout_request.assignment_id != assignment.pk:
            raise ConflictError("The checkout request's assignment changed. Please retry.")

        checkout_request.assignment = assignment

        if not AssignmentPolicy.can_resolve_checkout_request(actor, checkout_request):
            raise PermissionDenied(
                "You do not have permission to resolve this checkout request."
            )

        if checkout_request.status != CheckoutRequest.Status.PENDING:
            raise ConflictError("This checkout request has already been resolved.")

        if not isinstance(approve, bool):
            raise ValidationError("The decision must specify approval or rejection.")

        if not isinstance(decision_note, str):
            raise ValidationError("The decision note must be text.")

        now = timezone.now()
        decision_fields = ["status", "decided_by", "decided_at", "decision_note"]

        if approve:
            if not AssignmentPolicy.can_complete_checkout(actor, assignment):
                raise PermissionDenied("You do not have permission to complete checkout.")

            if assignment.status != Assignment.Status.CHECKED_IN:
                raise ConflictError("Checkout requires a checked-in assignment.")

            if departure_confirmed is not True:
                raise ValidationError("Confirm physical departure before approving checkout.")

            # An approved transfer may already hold a destination bed.
            # Resolve that transfer before releasing the source independently.
            if TransferRequest.objects.filter(
                source_assignment_id=assignment.pk,
                status=TransferRequest.Status.APPROVED,
            ).exists():
                raise ConflictError(
                    "Resolve the approved transfer before completing checkout."
                )

            assignment.status = Assignment.Status.CHECKED_OUT
            assignment.actual_check_out = now
            cls._save_assignment(
                assignment,
                fields=["status", "actual_check_out"],
            )

            checkout_request.status = CheckoutRequest.Status.APPROVED
            checkout_request.departure_verified_at = now
            decision_fields.append("departure_verified_at")
        else:
            checkout_request.status = CheckoutRequest.Status.REJECTED

        checkout_request.decided_by = actor
        checkout_request.decided_at = now
        checkout_request.decision_note = decision_note.strip()

        return cls._save_workflow_request(
            checkout_request,
            update_fields=decision_fields,
        )
        
    @staticmethod
    @transaction.atomic
    def flag_eligibility_review(*, student):
        """
        Flag the student's active commitments for review.

        Call this from the authorized student service, in the same
        transaction as a change that requires eligibility reassessment.
        """
        try:
            # Serialize with assignment operations for this student.
            lock_instance(student, mode="exclusive")
        except type(student).DoesNotExist as exc:
            raise NotFoundError("The student could not be found.") from exc

        return (
            Assignment.objects.filter(
                student_id=student.pk,
                status__in=[
                    Assignment.Status.RESERVED,
                    Assignment.Status.CHECKED_IN,
                ],
            )
            .exclude(review_status=Assignment.ReviewStatus.PENDING)
            .update(
                review_status=Assignment.ReviewStatus.PENDING,
                reviewed_by=None,
                reviewed_at=None,
                updated_at=timezone.now(),
            )
        )

    @classmethod
    @transaction.atomic
    def decide_eligibility_review(cls, *, actor, assignment, approve):
        """Record the decision on an active assignment's pending review."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_review_eligibility(actor, assignment):
            raise PermissionDenied(
                "You do not have permission to decide this eligibility review."
            )

        if assignment.status not in {
            Assignment.Status.RESERVED,
            Assignment.Status.CHECKED_IN,
        }:
            raise ConflictError("Eligibility review requires an active assignment.")

        if assignment.review_status != Assignment.ReviewStatus.PENDING:
            raise ConflictError("This assignment has no pending eligibility review.")

        if not isinstance(approve, bool):
            raise ValidationError("The decision must specify approval or rejection.")

        assignment.review_status = (
            Assignment.ReviewStatus.APPROVED
            if approve
            else Assignment.ReviewStatus.REJECTED
        )
        assignment.reviewed_by = actor
        assignment.reviewed_at = timezone.now()

        return cls._save_assignment(
            assignment,
            fields=["review_status", "reviewed_by", "reviewed_at"],
        )
        
    @staticmethod
    def _require_no_approved_transfer(assignment):
        """Prevent independent release while a transfer holds another bed."""
        if TransferRequest.objects.filter(
            source_assignment_id=assignment.pk,
            status=TransferRequest.Status.APPROVED,
        ).exists():
            raise ConflictError(
                "Resolve the approved transfer before releasing the assigned bed."
            )

    @classmethod
    @transaction.atomic
    def terminate_assignment(
        cls,
        *,
        actor,
        assignment,
        reason,
        departure_confirmed=False,
    ):
        """Administratively end a checked-in assignment after departure."""
        assignment = cls._get_locked_assignment(assignment.pk)

        if not AssignmentPolicy.can_terminate_assignment(actor, assignment):
            raise PermissionDenied(
                "You do not have permission to terminate this assignment."
            )

        if assignment.status != Assignment.Status.CHECKED_IN:
            raise ConflictError("Termination requires a checked-in assignment.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A termination reason is required.")

        if departure_confirmed is not True:
            raise ValidationError(
                "Confirm physical departure before terminating this assignment."
            )

        cls._require_no_approved_transfer(assignment)

        assignment.status = Assignment.Status.TERMINATED
        assignment.terminated_by = actor
        assignment.terminated_at = timezone.now()
        assignment.termination_reason = reason.strip()

        return cls._save_assignment(
            assignment,
            fields=[
                "status",
                "terminated_by",
                "terminated_at",
                "termination_reason",
            ],
        )