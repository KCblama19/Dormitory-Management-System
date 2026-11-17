from django.db.models import Q

from apps.assignments.models import AllocationRequest, Assignment, TransferRequest


def campus_has_unresolved_commitments(*, campus_id):
    """Check campus commitments while the caller holds the campus lock."""
    if Assignment.objects.filter(
        bed__room__floor__building__campus_id=campus_id,
        status__in=[
            Assignment.Status.RESERVED,
            Assignment.Status.CHECKED_IN,
        ],
    ).exists():
        return True

    if AllocationRequest.objects.filter(
        building__campus_id=campus_id,
        status__in=[
            AllocationRequest.Status.PENDING,
            AllocationRequest.Status.AWAITING_CONFIRMATION,
            AllocationRequest.Status.PARTIALLY_ALLOCATED,
        ],
    ).exists():
        return True

    # A pending transfer can involve this campus before approval has
    # created a destination reservation.
    return TransferRequest.objects.filter(
        Q(source_assignment__bed__room__floor__building__campus_id=campus_id)
        | Q(destination_bed__room__floor__building__campus_id=campus_id),
        status__in=[
            TransferRequest.Status.PENDING,
            TransferRequest.Status.APPROVED,
        ],
    ).exists()