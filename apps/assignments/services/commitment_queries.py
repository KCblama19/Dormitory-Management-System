from django.db.models import Q, OuterRef

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
    
def active_housing_assignments():
    """Return the Assignments that currently commit a bed."""
    return Assignment.objects.filter(
        status__in=(
            Assignment.Status.RESERVED,
            Assignment.Status.CHECKED_IN,
        ),
    )


def floor_has_active_assignments(*, floor_id):
    """Check floor commitments while the caller holds the exclusive floor lock."""
    return active_housing_assignments().filter(
        bed__room__floor_id=floor_id,
    ).exists()


def building_has_unresolved_commitments(*, building_id):
    """Check whether the building can be taken out of use.

    Call this while holding the exclusive building lock. A pending
    transfer can affect the building before a destination bed is reserved.
    """
    if Assignment.objects.filter(
        bed__room__floor__building_id=building_id,
        status__in=(
            Assignment.Status.RESERVED,
            Assignment.Status.CHECKED_IN,
        ),
    ).exists():
        return True

    if (
        AllocationRequest.objects.unresolved()
        .filter(building_id=building_id)
        .exists()
    ):
        return True

    return TransferRequest.objects.filter(
        Q(source_assignment__bed__room__floor__building_id=building_id)
        | Q(destination_bed__room__floor__building_id=building_id),
        status__in=(
            TransferRequest.Status.PENDING,
            TransferRequest.Status.APPROVED,
        ),
    ).exists()
    
def beds_requiring_valid_position(beds):
    """Return the beds whose positions must fit the current configuration.

    Retired beds keep their old positions for history. If an older record
    still has a live assignment, protect that commitment until it is resolved.
    """
    from apps.accommodations.models import Bed

    active_assignment = active_housing_assignments().filter(
        bed_id=OuterRef("pk"),
    )

    return beds.filter(
        ~Q(status=Bed.Status.RETIRED) | Exists(active_assignment)
    )