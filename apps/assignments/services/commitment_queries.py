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

    if AllocationRequest.objects.unresolved().filter(
        building__campus_id=campus_id,
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
    
def committed_bed_ids(*, bed_ids):
    """Return the supplied beds that are reserved or checked in.

    Callers changing inventory must hold the relevant room and bed locks
    before using this result to decide whether a change can proceed.
    """
    return set(
        Assignment.objects.filter(
            bed_id__in=bed_ids,
            status__in=(
                Assignment.Status.RESERVED,
                Assignment.Status.CHECKED_IN,
            ),
        )
        .order_by()
        .values_list("bed_id", flat=True)
    )