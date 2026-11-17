from datetime import date, datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

# DJANGO EXCEPTIONS
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError as DjangoValidationError,
)

# MODELS AND METHODS
from apps.accommodations.models import Bed, Building, Floor
from apps.assignments.models import Assignment, TransferRequest
from apps.assignments.services.assignment_service import (
    AssignmentService,
    _campus_local_date,
    _last_check_in_date,
)

# APPLICATION DB LOCKING 
from apps.core.db.locking import get_locked_instance, lock_rows

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)

# APPLICATION POLICIES
from apps.core.policies.transfer_policy import TransferPolicy
from apps.core.policies.assignment_policy import AssignmentPolicy


ACTIVE_ASSIGNMENT_STATUSES = (
    Assignment.Status.RESERVED,
    Assignment.Status.CHECKED_IN,
)
OPEN_TRANSFER_STATUSES = (
    TransferRequest.Status.PENDING,
    TransferRequest.Status.APPROVED,
)


def _bed_path(bed):
    room = bed.room
    floor = room.floor
    building = floor.building
    campus = building.campus
    return campus.university, campus, building, floor, room, bed


def _lock_transfer_context(*, source_id, destination_bed_id):
    """Lock both accommodation paths in the same order for every transfer."""
    sources = Assignment.objects.select_related(
        "student",
        "bed__room__floor__building__campus__university",
    )
    beds = Bed.objects.select_related("room__floor__building__campus__university")

    try:
        source = sources.get(pk=source_id)
        destination = beds.get(pk=destination_bed_id)
        student_id = source.student_id
        source_path = _bed_path(source.bed)
        destination_path = _bed_path(destination)

        lock_rows(type(source.student), [student_id], mode="exclusive")

        # Room locks serialize destination checks across beds in the
        # same room, including checks against current room occupants.
        for level, (left, right) in enumerate(
            zip(source_path, destination_path, strict=True)
        ):
            lock_rows(
                type(left),
                [left.pk, right.pk],
                mode="exclusive" if level == 4 else "shared",
            )

        lock_rows(Assignment, [source_id], mode="exclusive")

        source = sources.get(pk=source_id)
        destination = beds.get(pk=destination_bed_id)
    except ObjectDoesNotExist as exc:
        raise NotFoundError(
            "The source assignment or destination bed could not be found."
        ) from exc

    if (
        source.student_id != student_id
        or _bed_path(source.bed) != source_path
        or _bed_path(destination) != destination_path
    ):
        raise ConflictError("The transfer's accommodation changed. Please retry.")

    return source, destination

def _get_locked_transfer(transfer_id):
    """Lock the source, both accommodation paths, and the transfer."""
    try:
        reference = TransferRequest.objects.get(pk=transfer_id)
        source, destination = _lock_transfer_context(
            source_id=reference.source_assignment_id,
            destination_bed_id=reference.destination_bed_id,
        )
        transfer = get_locked_instance(
            TransferRequest,
            transfer_id,
            mode="exclusive",
        )
    except TransferRequest.DoesNotExist as exc:
        raise NotFoundError("The transfer request could not be found.") from exc

    if (
        transfer.source_assignment_id != source.pk
        or transfer.destination_bed_id != destination.pk
    ):
        raise ConflictError(
            "The transfer's source or destination changed. Please retry."
        )

    return transfer, source, destination

def _get_locked_destination_reservation(transfer, source, destination):
    try:
        reservation = Assignment.objects.select_for_update(
            of=("self",),
        ).get(transfer_request_id=transfer.pk)
    except Assignment.DoesNotExist as exc:
        raise ConflictError(
            "The approved transfer has no destination reservation."
        ) from exc

    if (
        reservation.student_id != source.student_id
        or reservation.bed_id != destination.pk
        or reservation.status != Assignment.Status.RESERVED
    ):
        raise ConflictError(
            "The destination reservation no longer matches this transfer."
        )

    return reservation

def _validate_destination(source, destination, *, destination_reservation=None):
    """Validate the destination against the locked housing and student state."""
    if source.status != Assignment.Status.CHECKED_IN:
        raise ConflictError("A transfer requires a checked-in source assignment.")
    
    active_assignments = Assignment.objects.filter(
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    )

    if destination_reservation is not None:
        active_assignments = active_assignments.exclude(
            pk=destination_reservation.pk,
        )
        
    if source.bed_id == destination.pk:
        raise ValidationError("Choose a destination other than the current bed.")

    university, campus, building, floor, room, _ = _bed_path(destination)
    student = source.student

    if (
        not university.is_active
        or not campus.is_active
        or not building.is_active
        or not floor.is_active
        or floor.status != Floor.FloorStatus.ACTIVE
        or floor.is_restricted
        or destination.status != Bed.Status.AVAILABLE
    ):
        raise ConflictError("The destination bed is unavailable for transfer.")

    if (
        student.admission_status != student.AdmissionStatus.ACCEPTED
        or student.eligibility_status != student.EligibilityStatus.ELIGIBLE
        or source.review_status in {
            Assignment.ReviewStatus.PENDING,
            Assignment.ReviewStatus.REJECTED,
        }
    ):
        raise ConflictError("The student is ineligible for transfer.")

    if not student.campus_assignments.filter(
        campus_id=campus.pk,
        academic_year__is_current=True,
        status="ACTIVE",
    ).exists():
        raise ValidationError(
            "The student must have an active academic assignment at the destination campus."
        )

    nationality = student.nationality.code
    if not nationality or (
        (nationality == "CN")
        != (building.student_population == Building.StudentPopulation.CHINESE)
    ):
        raise ValidationError("The student does not match the building's population policy.")

    gender_code = student.gender.code
    required_gender = {
        Building.GenderPolicy.MALE_ONLY: "M",
        Building.GenderPolicy.FEMALE_ONLY: "F",
    }.get(building.gender_policy)

    if required_gender is None:
        required_gender = {
            Floor.GenderConfiguration.MALE: "M",
            Floor.GenderConfiguration.FEMALE: "F",
        }.get(floor.gender_configuration)

    if required_gender is not None and gender_code != required_gender:
        raise ValidationError("The student does not match the destination's gender policy.")

    if active_assignments.filter(bed_id=destination.pk).exists():
        raise ConflictError("The destination bed already has an active assignment.")

    if active_assignments.filter(student_id=student.pk).exclude(pk=source.pk).exists():
        raise ConflictError("The student already has another active assignment.")

    if active_assignments.filter(bed__room_id=room.pk).exclude(
        student__gender__code=gender_code,
    ).exists():
        raise ConflictError("The destination room has incompatible active assignments.")


def _validate_move_date(move_date, *, local_date):
    if not isinstance(move_date, date) or isinstance(move_date, datetime):
        raise ValidationError("Supply a calendar date for the move.")

    if move_date < local_date:
        raise ValidationError("The move date cannot be in the past.")


class TransferService:
    @staticmethod
    @transaction.atomic
    def request_transfer(
        *,
        actor,
        source_assignment,
        destination_bed,
        reason,
        requested_move_date=None,
    ):
        source, destination = _lock_transfer_context(
            source_id=source_assignment.pk,
            destination_bed_id=destination_bed.pk,
        )
        _, campus, building, _, _, _ = _bed_path(destination)

        if not TransferPolicy.can_request_transfer(
            actor, source=source, destination_building=building,
        ):
            raise PermissionDenied("You do not have permission to request this transfer.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A transfer reason is required.")

        if requested_move_date is not None or TransferPolicy.is_student_account(actor):
            _validate_move_date(
                requested_move_date,
                local_date=_campus_local_date(campus, timezone.now()),
            )

        if TransferRequest.objects.filter(status__in=OPEN_TRANSFER_STATUSES).filter(
            Q(source_assignment_id=source.pk) | Q(destination_bed_id=destination.pk)
        ).exists():
            raise ConflictError("The source or destination already has an open transfer.")

        _validate_destination(source, destination)

        return AssignmentService._save_workflow_request(
            TransferRequest(
                source_assignment=source,
                destination_bed=destination,
                initiated_by=actor,
                transfer_reason=reason.strip(),
                requested_move_date=requested_move_date,
            )
        )

    @staticmethod
    @transaction.atomic
    def approve_transfer(*, actor, transfer_request, approved_move_date):
        try:
            reference = TransferRequest.objects.get(pk=transfer_request.pk)
            source, destination = _lock_transfer_context(
                source_id=reference.source_assignment_id,
                destination_bed_id=reference.destination_bed_id,
            )
            transfer = get_locked_instance(
                TransferRequest, reference.pk, mode="exclusive",
            )
        except TransferRequest.DoesNotExist as exc:
            raise NotFoundError("The transfer request could not be found.") from exc

        if (
            transfer.source_assignment_id != source.pk
            or transfer.destination_bed_id != destination.pk
        ):
            raise ConflictError("The transfer's source or destination changed. Please retry.")

        _, campus, building, _, _, _ = _bed_path(destination)

        if not TransferPolicy.can_approve_transfer(
            actor, source=source, destination_building=building,
        ):
            raise PermissionDenied("You do not have permission to approve this transfer.")

        if transfer.status != TransferRequest.Status.PENDING:
            raise ConflictError("Only a pending transfer can be approved.")
        
        if transfer.cancellation_requested_at is not None:
            raise ConflictError("Process the pending transfer cancellation first.")

        now = timezone.now()
        _validate_move_date(
            approved_move_date,
            local_date=_campus_local_date(campus, now),
        )

        if source.expected_check_out and approved_move_date >= source.expected_check_out:
            raise ValidationError("The move date must be before the planned checkout date.")

        _validate_destination(source, destination)

        transfer.status = TransferRequest.Status.APPROVED
        transfer.approved_move_date = approved_move_date
        transfer.decided_by = actor
        transfer.decided_at = now

        AssignmentService._save_workflow_request(
            transfer,
            update_fields=["status", "approved_move_date", "decided_by", "decided_at"],
        )

        reservation = Assignment(
            student=source.student,
            bed=destination,
            transfer_request=transfer,
            status=Assignment.Status.RESERVED,
            expected_check_in=approved_move_date,
            expected_check_out=source.expected_check_out,
            check_in_deadline=approved_move_date,
            grace_period_days=source.grace_period_days,
            reserved_at=now,
        )

        try:
            with transaction.atomic():
                reservation.full_clean()
                reservation.save(force_insert=True)
        except DjangoValidationError as exc:
            raise ValidationError(" ".join(exc.messages)) from exc
        except IntegrityError as exc:
            raise ConflictError("The destination bed could not be reserved.") from exc

        return transfer
    
    @staticmethod
    @transaction.atomic
    def complete_transfer(
        *,
        actor,
        transfer_request,
        move_confirmed=False,
        approve_early=False,
    ):
        """Complete a verified physical move between the two assignments."""
        transfer, source, destination = _get_locked_transfer(transfer_request.pk)
        _, campus, building, _, _, _ = _bed_path(destination)

        if not TransferPolicy.can_complete_transfer(
            actor,
            source=source,
            destination_building=building,
        ):
            raise PermissionDenied(
                "You do not have permission to complete this transfer."
            )

        if transfer.status != TransferRequest.Status.APPROVED:
            raise ConflictError("Only an approved transfer can be completed.")
        
        if transfer.cancellation_requested_at is not None:
            raise ConflictError("Process the pending transfer cancellation first.")
        
        if move_confirmed is not True:
            raise ValidationError(
                "Confirm that the student has vacated the source and "
                "moved into the destination."
            )

        try:
            destination_assignment = Assignment.objects.select_for_update(
                of=("self",),
            ).get(transfer_request_id=transfer.pk)
        except Assignment.DoesNotExist as exc:
            raise ConflictError(
                "The approved transfer has no destination reservation."
            ) from exc

        if (
            destination_assignment.student_id != source.student_id
            or destination_assignment.bed_id != destination.pk
            or destination_assignment.status != Assignment.Status.RESERVED
        ):
            raise ConflictError(
                "The destination reservation no longer matches this transfer."
            )

        if destination_assignment.review_status in {
            Assignment.ReviewStatus.PENDING,
            Assignment.ReviewStatus.REJECTED,
        }:
            raise ConflictError(
                "Resolve the destination's eligibility review before completing the move."
            )

        _validate_destination(
            source,
            destination,
            destination_reservation=destination_assignment,
        )

        # Use a fresh timestamp after acquiring the locks. The grace
        # period includes the entire final day in the configured timezone.
        now = timezone.now()
        local_date = _campus_local_date(campus, now)

        if local_date > _last_check_in_date(destination_assignment):
            raise ConflictError("The destination reservation's grace period has ended.")

        is_early = local_date < destination_assignment.expected_check_in

        if is_early:
            if approve_early is not True:
                raise ValidationError("An early move requires explicit approval.")

            destination_assignment.bed = destination
            if not AssignmentPolicy.can_approve_early_check_in(
                actor,
                destination_assignment,
            ):
                raise PermissionDenied("You do not have permission to approve an early move.")

        # Close the source first so the student never has two checked-in
        # assignments. A failure later in the transaction restores it.
        source.status = Assignment.Status.CHECKED_OUT
        source.actual_check_out = now
        AssignmentService._save_assignment(
            source,
            fields=["status", "actual_check_out"],
        )

        destination_assignment.status = Assignment.Status.CHECKED_IN
        destination_assignment.actual_check_in = now
        destination_assignment.early_check_in_approved_by = actor if is_early else None
        AssignmentService._save_assignment(
            destination_assignment,
            fields=["status", "actual_check_in", "early_check_in_approved_by"],
        )

        transfer.status = TransferRequest.Status.COMPLETED
        transfer.completed_by = actor
        transfer.completed_at = now
        return AssignmentService._save_workflow_request(
            transfer,
            update_fields=["status", "completed_by", "completed_at"],
        )
        
    @staticmethod
    @transaction.atomic
    def reject_transfer(*, actor, transfer_request):
        """Reject a pending transfer before a destination is reserved."""
        transfer, source, destination = _get_locked_transfer(transfer_request.pk)
        building = destination.room.floor.building

        if not TransferPolicy.can_approve_transfer(
            actor, source=source, destination_building=building,
        ):
            raise PermissionDenied("You do not have permission to reject this transfer.")

        if transfer.status != TransferRequest.Status.PENDING:
            raise ConflictError("Only a pending transfer can be rejected.")

        if transfer.cancellation_requested_at is not None:
            raise ConflictError("Process the pending transfer cancellation first.")

        transfer.status = TransferRequest.Status.REJECTED
        transfer.decided_by = actor
        transfer.decided_at = timezone.now()

        return AssignmentService._save_workflow_request(
            transfer,
            update_fields=["status", "decided_by", "decided_at"],
        )

    @staticmethod
    @transaction.atomic
    def request_transfer_cancellation(*, actor, transfer_request, reason):
        """Record a student's request for staff to cancel a same-building move."""
        transfer, source, destination = _get_locked_transfer(transfer_request.pk)
        building = destination.room.floor.building

        if not TransferPolicy.can_request_transfer_cancellation(
            actor, source=source, destination_building=building,
        ):
            raise PermissionDenied(
                "You can only request cancellation of your own same-building transfer."
            )

        if transfer.status not in OPEN_TRANSFER_STATUSES:
            raise ConflictError("Only an open transfer can be cancelled.")

        if transfer.cancellation_requested_at is not None:
            raise ConflictError("A cancellation has already been requested.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A cancellation reason is required.")

        transfer.cancellation_requested_by = actor
        transfer.cancellation_requested_at = timezone.now()
        transfer.cancellation_reason = reason.strip()

        return AssignmentService._save_workflow_request(
            transfer,
            update_fields=[
                "cancellation_requested_by",
                "cancellation_requested_at",
                "cancellation_reason",
            ],
        )

    @staticmethod
    @transaction.atomic
    def cancel_transfer(*, actor, transfer_request, reason=None):
        """Cancel a transfer and release its destination reservation, if any."""
        transfer, source, destination = _get_locked_transfer(transfer_request.pk)
        building = destination.room.floor.building

        if not TransferPolicy.can_cancel_transfer(
            actor, source=source, destination_building=building,
        ):
            raise PermissionDenied("You do not have permission to cancel this transfer.")

        if transfer.status not in OPEN_TRANSFER_STATUSES:
            raise ConflictError("Only an open transfer can be cancelled.")

        # Preserve the student's reason when staff processes their request.
        if transfer.cancellation_requested_at is not None:
            reason = transfer.cancellation_reason

        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("A cancellation reason is required.")

        reason = reason.strip()
        now = timezone.now()

        if transfer.status == TransferRequest.Status.APPROVED:
            reservation = _get_locked_destination_reservation(
                transfer, source, destination,
            )
            reservation.status = Assignment.Status.CANCELLED
            reservation.cancelled_by = actor
            reservation.cancelled_at = now
            reservation.cancellation_reason = reason

            AssignmentService._save_assignment(
                reservation,
                fields=["status", "cancelled_by", "cancelled_at", "cancellation_reason"],
            )

        transfer.status = TransferRequest.Status.CANCELLED
        transfer.cancelled_by = actor
        transfer.cancelled_at = now
        transfer.cancellation_reason = reason

        return AssignmentService._save_workflow_request(
            transfer,
            update_fields=["status", "cancelled_by", "cancelled_at", "cancellation_reason"],
        )

    @staticmethod
    @transaction.atomic
    def process_transfer_deadline(*, transfer_id):
        """Mark the destination overdue or expire it with the transfer."""
        transfer, source, destination = _get_locked_transfer(transfer_id)

        if transfer.status != TransferRequest.Status.APPROVED:
            return None

        reservation = _get_locked_destination_reservation(
            transfer, source, destination,
        )
        _, campus, _, _, _, _ = _bed_path(destination)
        now = timezone.now()
        local_date = _campus_local_date(campus, now)

        if local_date > _last_check_in_date(reservation):
            reservation.status = Assignment.Status.EXPIRED
            reservation.expired_at = now
            AssignmentService._save_assignment(
                reservation,
                fields=["status", "expired_at"],
            )

            transfer.status = TransferRequest.Status.EXPIRED
            AssignmentService._save_workflow_request(
                transfer,
                update_fields=["status"],
            )
            return "expired"

        if (
            local_date > reservation.check_in_deadline
            and reservation.overdue_at is None
        ):
            reservation.overdue_at = now
            AssignmentService._save_assignment(
                reservation,
                fields=["overdue_at"],
            )
            return "overdue"

        return None