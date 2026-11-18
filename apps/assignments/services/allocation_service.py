from collections.abc import Mapping
from datetime import date, datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accommodations.models import Bed, Building, Floor, Room
from apps.accommodations.models.campus.campus_model import Campus
from apps.assignments.models import AllocationRequest, AllocationRequestMember, Assignment
from apps.assignments.services.assignment_service import (
    AssignmentService,
    _campus_local_date,
)
from apps.core.db.locking import get_locked_instance
from apps.core.exceptions import ConflictError, NotFoundError, PermissionDenied, ValidationError
from apps.core.policies.allocation_policy import AllocationPolicy
from apps.profiles.student.models.campus_assignment import StudentAssignCampus
from apps.profiles.student.models.student_models import Student
from apps.university.models import University


ACTIVE_ASSIGNMENT_STATUSES = (Assignment.Status.RESERVED, Assignment.Status.CHECKED_IN)


class _RoomUnavailable(Exception):
    """Exit a candidate savepoint and release the locks taken in it."""


def _student_ids(students):
    """Read the submitted student IDs in the order supplied by the caller."""
    ids = [student.pk for student in students]
    if not ids or None in ids:
        raise ValidationError("Supply at least one saved student.")
    if len(set(ids)) != len(ids):
        raise ValidationError("Each student can appear only once in an allocation.")
    return ids


def _lock_allocation_context(student_ids, building_id):
    """Lock students first, followed by their destination's parent rows."""
    try:
        students = {
            pk: get_locked_instance(Student, pk, mode="exclusive")
            for pk in sorted(student_ids)
        }

        # The first read tells us which parent rows to lock. Verify the path
        # again after those locks are in place.
        reference = Building.objects.select_related("campus").get(pk=building_id)
        campus_id = reference.campus_id
        university_id = reference.campus.university_id
        university = get_locked_instance(University, university_id, mode="shared")
        campus = get_locked_instance(Campus, campus_id, mode="shared")
        building = get_locked_instance(Building, building_id, mode="shared")
    except ObjectDoesNotExist as exc:
        raise NotFoundError(
            "A student or the requested accommodation could not be found."
        ) from exc

    if campus.university_id != university.pk or building.campus_id != campus.pk:
        raise ConflictError("The building's accommodation hierarchy changed. Please retry.")

    return [students[pk] for pk in student_ids], university, campus, building


def _require_operational_building(university, campus, building):
    """Reject a destination whose building, campus, or university is inactive."""
    if not (university.is_active and campus.is_active and building.is_active):
        raise ConflictError("The requested building is not operational.")


def _validate_dates(
    *,
    expected_check_in,
    expected_check_out,
    check_in_deadline,
    grace_period_days,
    local_today,
):
    """Check the planned reservation dates against the campus calendar."""
    planned_dates = {
        "Expected check-in": expected_check_in,
        "Check-in deadline": check_in_deadline,
    }
    if expected_check_out is not None:
        planned_dates["Expected checkout"] = expected_check_out

    for label, value in planned_dates.items():
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValidationError(f"{label} must be a calendar date.")

    if type(grace_period_days) is not int or grace_period_days < 0:
        raise ValidationError("Grace period days must be a non-negative integer.")

    if expected_check_in < local_today:
        raise ValidationError("Expected check-in cannot be in the past.")

    if check_in_deadline < expected_check_in:
        raise ValidationError("The check-in deadline cannot precede expected check-in.")

    if expected_check_out is not None and expected_check_out <= expected_check_in:
        raise ValidationError("Expected checkout must be after expected check-in.")

    try:
        check_in_deadline + timedelta(days=grace_period_days)
    except OverflowError as exc:
        raise ValidationError("The final grace date is outside the supported range.") from exc


def _validate_student(student, campus, building, start_date):
    """Check eligibility for the requested campus and return the housing gender."""
    account = student.user
    if (
        not account.is_active
        or account.accountStatus != "ACTIVE"
        or account.account_type != "STUDENT"
        or student.admission_status != Student.AdmissionStatus.ACCEPTED
        or student.eligibility_status != Student.EligibilityStatus.ELIGIBLE
    ):
        raise ValidationError("The student is ineligible for accommodation allocation.")

    status = StudentAssignCampus.AssignmentStatus
    # A campus transfer ends the old record on the day the new one starts.
    # An open-ended record still expires with the academic year.
    covers_start = (
        student.campus_assignments.filter(
            campus_id=campus.pk,
            start_date__lte=start_date,
            academic_year__start_date__lte=start_date,
            academic_year__end_date__gte=start_date,
        )
        .filter(
            Q(status=status.ACTIVE, end_date__isnull=True)
            | Q(
                status__in=(status.ACTIVE, status.ENDED, status.TRANSFERRED),
                end_date__gt=start_date,
            )
        )
        .exists()
    )
    if not covers_start:
        raise ValidationError(
            "The student must be assigned to this campus on the expected check-in date."
        )

    nationality = student.nationality.code
    population = (
        Building.StudentPopulation.CHINESE
        if nationality == "CN"
        else Building.StudentPopulation.INTERNATIONAL
    )
    if not nationality or building.student_population != population:
        raise ValidationError("The student does not match the building's population policy.")

    gender = student.gender.code
    if gender not in {"M", "F"}:
        raise ValidationError("The student must have a supported housing gender code.")

    required_gender = {
        Building.GenderPolicy.MALE_ONLY: "M",
        Building.GenderPolicy.FEMALE_ONLY: "F",
    }.get(building.gender_policy)
    if required_gender is not None and gender != required_gender:
        raise ValidationError("The student does not match the building's gender policy.")

    return gender


def _validate_members(students, campus, building, start_date, allow_partial, *, request_id=None):
    """Check each member and group together students who can share a room."""
    students_by_gender = {}
    for student in students:
        gender = _validate_student(student, campus, building, start_date)
        students_by_gender.setdefault(gender, []).append(student.pk)

    if len(students_by_gender) > 1 and not allow_partial:
        raise ValidationError(
            "All group members must be compatible with the same room gender policy."
        )

    student_ids = [student.pk for student in students]
    if Assignment.objects.filter(
        student_id__in=student_ids,
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    ).exists():
        message = (
            "The student already has an active assignment."
            if len(students) == 1
            else "A group member already has an active assignment."
        )
        raise ConflictError(message)

    unresolved = AllocationRequestMember.objects.unresolved().filter(student_id__in=student_ids)
    if request_id is not None:
        unresolved = unresolved.exclude(allocation_request_id=request_id)

    if unresolved.exists():
        message = (
            "The student already has an unresolved allocation request."
            if len(students) == 1
            else "A group member already has an unresolved allocation request."
        )
        raise ConflictError(message)

    return students_by_gender


def _lock_room_inventory(building, floor_id, room_id):
    """Lock the floor and room before checking occupants or touching beds."""
    floor = get_locked_instance(Floor, floor_id, mode="shared")
    room = get_locked_instance(Room, room_id, mode="exclusive")
    if (
        floor.building_id != building.pk
        or room.floor_id != floor.pk
        or not floor.is_active
        or floor.status != Floor.FloorStatus.ACTIVE
        or floor.is_restricted
    ):
        raise _RoomUnavailable

    floor_gender = None
    if building.gender_policy == Building.GenderPolicy.MIXED:
        floor_gender = {
            Floor.GenderConfiguration.MALE: "M",
            Floor.GenderConfiguration.FEMALE: "F",
        }.get(floor.gender_configuration)

    # A reserved bed counts here just like an occupied bed. Holding the room
    # lock prevents another allocation from changing who can share the room.
    commitments = Assignment.objects.filter(
        bed__room_id=room.pk,
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    )
    roommate_genders = set(
        commitments.order_by().values_list("student__gender__code", flat=True).distinct()
    )
    return room, floor_gender, roommate_genders, commitments


def _lock_beds(room, bed_ids):
    """Lock the specific beds in primary-key order and check them again."""
    beds = {
        pk: get_locked_instance(Bed, pk, mode="exclusive")
        for pk in sorted(bed_ids)
    }
    if any(bed.room_id != room.pk or bed.status != Bed.Status.AVAILABLE for bed in beds.values()):
        raise _RoomUnavailable

    if Assignment.objects.filter(
        bed_id__in=beds,
        status__in=ACTIVE_ASSIGNMENT_STATUSES,
    ).exists():
        raise _RoomUnavailable
    return beds


def _select_beds(building, students_by_gender, group_size, allow_partial):
    """Find the largest permitted group of beds together in one room."""
    active_assignments = Assignment.objects.filter(status__in=ACTIVE_ASSIGNMENT_STATUSES)
    minimum_beds = 1 if allow_partial else group_size
    candidates = list(
        Bed.objects.filter(
            room__floor__building_id=building.pk,
            room__floor__is_active=True,
            room__floor__status=Floor.FloorStatus.ACTIVE,
            room__floor__is_restricted=False,
            status=Bed.Status.AVAILABLE,
        )
        .exclude(pk__in=active_assignments.order_by().values("bed_id"))
        .values("room__floor_id", "room_id")
        .annotate(available_count=Count("pk"))
        .filter(available_count__gte=minimum_beds)
        .order_by("room__floor_id", "room_id")
        .values_list("room__floor_id", "room_id", "available_count")
    )

    largest_room = max((count for _, _, count in candidates), default=0)
    largest_compatible_group = max(map(len, students_by_gender.values()))
    largest_attempt = min(largest_room, largest_compatible_group)

    # Prefer serving more students. For equal sizes, try rooms in inventory
    # order and keep the caller's student order within the selected group.
    for required_beds in range(largest_attempt, minimum_beds - 1, -1):
        for floor_id, room_id, available_count in candidates:
            if available_count < required_beds:
                continue

            try:
                with transaction.atomic():
                    room, floor_gender, roommates, commitments = _lock_room_inventory(
                        building, floor_id, room_id
                    )
                    matching = next(
                        (
                            student_ids
                            for gender, student_ids in students_by_gender.items()
                            if len(student_ids) >= required_beds
                            and floor_gender in (None, gender)
                            and roommates <= {gender}
                        ),
                        None,
                    )
                    if matching is None:
                        raise _RoomUnavailable

                    bed_ids = list(
                        Bed.objects.filter(room_id=room.pk, status=Bed.Status.AVAILABLE)
                        .exclude(pk__in=commitments.order_by().values("bed_id"))
                        .order_by("pk")
                        .values_list("pk", flat=True)[:required_beds]
                    )
                    if len(bed_ids) != required_beds:
                        raise _RoomUnavailable

                    beds = _lock_beds(room, bed_ids)
                    return dict(
                        zip(matching[:required_beds], (beds[pk] for pk in bed_ids), strict=True)
                    )
            except (_RoomUnavailable, ObjectDoesNotExist):
                # A failed candidate must release its floor and room locks
                # before we go back to the start of the lock order.
                continue

    if group_size == 1:
        raise ConflictError("No compatible bed is available in this building.")

    if allow_partial:
        raise ConflictError("No room can accommodate any members of this group.")

    raise ConflictError("No compatible room has enough available beds for the entire group.")


def _lock_proposed_beds(building, proposals, students_by_gender):
    """Lock the proposed beds and recheck their room and student compatibility."""
    proposed_ids = set(proposals.values())
    selected_ids = set(proposals)
    if not proposals or len(proposed_ids) != len(proposals):
        raise ConflictError("The proposal contains invalid or duplicate beds.")

    paths = set(
        Bed.objects.filter(pk__in=proposed_ids).values_list("room__floor_id", "room_id")
    )
    if len(paths) != 1:
        raise ConflictError("The proposed beds must belong to one room. Review the selection.")

    floor_id, room_id = paths.pop()
    try:
        room, floor_gender, roommates, _ = _lock_room_inventory(building, floor_id, room_id)
        if not any(
            selected_ids <= set(student_ids)
            and floor_gender in (None, gender)
            and roommates <= {gender}
            for gender, student_ids in students_by_gender.items()
        ):
            raise _RoomUnavailable

        beds = _lock_beds(room, proposed_ids)
    except (_RoomUnavailable, ObjectDoesNotExist) as exc:
        raise ConflictError(
            "A proposed bed is no longer suitable or available. Review the selection."
        ) from exc

    return {student_id: beds[bed_id] for student_id, bed_id in proposals.items()}


def _prepare_manual_beds(building, selection, students_by_gender, allow_partial):
    """Check that staff selected distinct saved beds for the intended members."""
    if not isinstance(selection, Mapping) or not selection:
        raise ValidationError("Select at least one bed using student and bed primary keys.")

    proposals = dict(selection)
    student_ids = {pk for ids in students_by_gender.values() for pk in ids}
    if proposals.keys() - student_ids:
        raise ValidationError("Beds can only be selected for students on this request.")
    if not allow_partial and proposals.keys() != student_ids:
        raise ValidationError("Select a bed for every student on this request.")

    try:
        # Normalize form values before comparing them. A UUID and its string
        # representation identify the same physical bed.
        proposals = {
            student_id: Bed._meta.pk.to_python(bed_id)
            for student_id, bed_id in proposals.items()
        }
        unique_bed_ids = set(proposals.values())
    except (DjangoValidationError, TypeError, ValueError) as exc:
        raise ValidationError("Select beds using their primary keys.") from exc
    if None in unique_bed_ids or len(unique_bed_ids) != len(proposals):
        raise ValidationError("Select a distinct saved bed for each selected student.")

    return _lock_proposed_beds(building, proposals, students_by_gender)


def _save_assignment_for_member(member, bed, schedule, now):
    """Create the reservation, then record the member's completed outcome."""
    reservation = Assignment(
        student_id=member.student_id,
        bed=bed,
        allocation_member=member,
        status=Assignment.Status.RESERVED,
        reserved_at=now,
        **schedule,
    )
    try:
        with transaction.atomic():
            reservation.full_clean()
            reservation.save(force_insert=True)
    except DjangoValidationError as exc:
        raise ValidationError(" ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise ConflictError("The selected bed could not be reserved.") from exc

    member.assigned_bed = bed
    member.resolved_at = now
    member.status = AllocationRequestMember.Status.ALLOCATED
    AssignmentService._save_workflow_request(
        member, update_fields=["assigned_bed", "resolved_at", "status"]
    )
    return reservation


def _finalize(request, members, beds_by_student, schedule, actor, now):
    """Reserve the selected beds and set the parent outcome in one transaction."""
    reservations = [
        _save_assignment_for_member(member, beds_by_student[member.student_id], schedule, now)
        for member in members
        if member.student_id in beds_by_student
    ]

    _save_request_outcome(request, members, actor, now)
    return reservations


def _open_members(members):
    """Return the members whose allocation outcome still needs a decision."""
    return [
        member for member in members
        if member.status in AllocationRequestMember.UNRESOLVED_STATUSES
    ]


def _save_request_outcome(request, members, actor, now):
    """Set the request status from its members and record the closing decision."""
    status = AllocationRequest.Status
    member_status = AllocationRequestMember.Status
    outcomes = {member.status for member in members}
    has_open_members = bool(outcomes.intersection(AllocationRequestMember.UNRESOLVED_STATUSES))

    # A partial request represents the same historical outcome after its
    # last pending member is resolved. The member states tell us whether
    # it remains open, and the closing decision is recorded only once.
    if outcomes == {member_status.ALLOCATED}:
        request.status = status.COMPLETED
    elif member_status.ALLOCATED in outcomes:
        request.status = status.PARTIALLY_ALLOCATED
    elif member_status.AWAITING_CONFIRMATION in outcomes:
        request.status = status.AWAITING_CONFIRMATION
    elif has_open_members:
        request.status = status.PENDING
    elif member_status.REJECTED in outcomes:
        request.status = status.REJECTED
    else:
        request.status = status.CANCELLED

    if not has_open_members:
        request.decided_by = actor
        request.decided_at = now

    return AssignmentService._save_workflow_request(
        request, update_fields=["status", "decided_by", "decided_at"]
    )


def _write_proposals(request, members, beds_by_student):
    """Record proposed beds and leave unselected members pending."""
    status = AllocationRequestMember.Status
    for member in _open_members(members):
        bed = beds_by_student.get(member.student_id)
        member.assigned_bed = bed
        member.status = status.AWAITING_CONFIRMATION if bed is not None else status.PENDING
        AssignmentService._save_workflow_request(
            member, update_fields=["assigned_bed", "status"]
        )

    request.status = AllocationRequest.Status.AWAITING_CONFIRMATION
    return AssignmentService._save_workflow_request(request, update_fields=["status"])


def _proposal_state(members):
    """Read the saved proposal, checking that bed choices match member status."""
    status = AllocationRequestMember.Status
    proposal = {}
    for member in members:
        if member.status == status.AWAITING_CONFIRMATION and member.assigned_bed_id is not None:
            proposal[member.student_id] = member.assigned_bed_id
        elif member.status != status.PENDING or member.assigned_bed_id is not None:
            raise ConflictError("The proposal has an invalid member outcome.")
    return proposal


def _require_open_proposal(request, strategy):
    """Check the saved strategy and ensure the proposal still needs a decision."""
    if (
        request.source != AllocationRequest.Source.ADMINISTRATIVE
        or request.allocation_strategy != strategy
        or request.status not in (
            AllocationRequest.Status.PENDING,
            AllocationRequest.Status.AWAITING_CONFIRMATION,
        )
    ):
        raise ConflictError("This request has no open proposal for this allocation strategy.")


def _request_context(request_id):
    """Read the request after locking its students and accommodation parents."""
    try:
        reference = AllocationRequest.objects.get(pk=request_id)
    except AllocationRequest.DoesNotExist as exc:
        raise NotFoundError("The allocation request could not be found.") from exc

    student_ids = list(
        reference.members.order_by("created_at", "pk").values_list("student_id", flat=True)
    )
    if not student_ids:
        raise ConflictError("The allocation request has no members.")

    students, university, campus, building = _lock_allocation_context(
        student_ids, reference.building_id
    )
    try:
        request = AllocationRequest.objects.get(pk=request_id)
    except AllocationRequest.DoesNotExist as exc:
        raise NotFoundError("The allocation request could not be found.") from exc

    members = tuple(request.members.order_by("created_at", "pk"))
    if request.building_id != building.pk or [member.student_id for member in members] != student_ids:
        raise ConflictError("The request changed while it was being opened. Please retry.")

    schedule = {
        "expected_check_in": request.expected_check_in,
        "expected_check_out": request.expected_check_out,
        "check_in_deadline": request.check_in_deadline,
        "grace_period_days": request.grace_period_days,
    }
    return request, members, students, university, campus, building, schedule


def _lock_workflow(request, members):
    """Lock the request and member rows after the selected inventory is locked."""
    previous_state = {
        member.pk: (member.student_id, member.status, member.assigned_bed_id, member.resolved_at)
        for member in members
    }
    request_fields = (
        "building_id",
        "status",
        "allocation_strategy",
        "source",
        "requested_by_id",
        "request_type",
        "allow_partial",
        "expected_check_in",
        "expected_check_out",
        "check_in_deadline",
        "grace_period_days",
    )

    try:
        locked_request = get_locked_instance(AllocationRequest, request.pk, mode="exclusive")
    except AllocationRequest.DoesNotExist as exc:
        raise NotFoundError("The allocation request could not be found.") from exc

    locked_members = {
        member.pk: member
        for member in locked_request.members.select_for_update().order_by("pk")
    }
    current_state = {
        member.pk: (member.student_id, member.status, member.assigned_bed_id, member.resolved_at)
        for member in locked_members.values()
    }
    if previous_state != current_state or any(
        getattr(locked_request, field) != getattr(request, field) for field in request_fields
    ):
        raise ConflictError("The request changed. Reload it before trying again.")

    return locked_request, [locked_members[member.pk] for member in members]


def _local_write_time(campus, expected_check_in):
    """Check the start date again after waiting for inventory and workflow locks."""
    now = timezone.now()
    if expected_check_in < _campus_local_date(campus, now):
        raise ValidationError("Expected check-in cannot be in the past.")
    return now


class AllocationService:
    """Prepare and finalize administrative accommodation allocations."""

    @staticmethod
    def execute_automatic_allocation(
        *,
        actor,
        student,
        building,
        expected_check_in,
        check_in_deadline,
        expected_check_out=None,
        grace_period_days=0,
        notes="",
    ) -> Assignment:
        """Reserve one compatible bed and return the student's Assignment."""
        return AllocationService._start_allocation(
            actor=actor,
            students=(student,),
            building=building,
            strategy=AllocationRequest.AllocationStrategy.AUTOMATIC,
            allow_partial=False,
            notes=notes,
            expected_check_in=expected_check_in,
            expected_check_out=expected_check_out,
            check_in_deadline=check_in_deadline,
            grace_period_days=grace_period_days,
        )[0]

    @staticmethod
    def execute_automatic_group_allocation(
        *,
        actor,
        students,
        building,
        expected_check_in,
        check_in_deadline,
        expected_check_out=None,
        grace_period_days=0,
        notes="",
        allow_partial=False,
    ) -> list[Assignment]:
        """Reserve beds in one room for a group of at least two students.

        Set allow_partial only after confirming the group's consent. Any
        student left without a bed stays pending on the same request.
        """
        students = tuple(students)
        if len(students) < 2:
            raise ValidationError("Group allocation requires at least two students.")

        return AllocationService._start_allocation(
            actor=actor,
            students=students,
            building=building,
            strategy=AllocationRequest.AllocationStrategy.AUTOMATIC,
            allow_partial=allow_partial,
            notes=notes,
            expected_check_in=expected_check_in,
            expected_check_out=expected_check_out,
            check_in_deadline=check_in_deadline,
            grace_period_days=grace_period_days,
        )

    @staticmethod
    def generate_recommendations(
        *,
        actor,
        students,
        building,
        expected_check_in,
        check_in_deadline,
        expected_check_out=None,
        grace_period_days=0,
        notes="",
        allow_partial=False,
    ) -> AllocationRequest:
        """Save a proposed set of beds for a manager to review.

        Pass one student for an individual request or several for a group.
        The recommendation records the planned dates and student-to-bed
        selections. Other workflows can still reserve the suggested beds.
        """
        return AllocationService._start_allocation(
            actor=actor,
            students=tuple(students),
            building=building,
            strategy=AllocationRequest.AllocationStrategy.RECOMMENDED,
            allow_partial=allow_partial,
            notes=notes,
            expected_check_in=expected_check_in,
            expected_check_out=expected_check_out,
            check_in_deadline=check_in_deadline,
            grace_period_days=grace_period_days,
        )

    @staticmethod
    def prepare_manual_allocation(
        *,
        actor,
        students,
        building,
        selected_beds_by_student,
        expected_check_in,
        check_in_deadline,
        expected_check_out=None,
        grace_period_days=0,
        notes="",
        allow_partial=False,
    ) -> AllocationRequest:
        """Save the beds staff selected for a manager to review.

        Pass the full list of students and a mapping from student primary
        keys to bed primary keys. A partial selection requires the group's
        consent. The beds remain available until the selection is approved.
        """
        return AllocationService._start_allocation(
            actor=actor,
            students=tuple(students),
            building=building,
            strategy=AllocationRequest.AllocationStrategy.MANUAL,
            allow_partial=allow_partial,
            notes=notes,
            selected_beds_by_student=selected_beds_by_student,
            expected_check_in=expected_check_in,
            expected_check_out=expected_check_out,
            check_in_deadline=check_in_deadline,
            grace_period_days=grace_period_days,
        )

    @staticmethod
    @transaction.atomic
    def _start_allocation(
        *, actor, students, building, strategy, allow_partial, notes,
        selected_beds_by_student=None, **schedule,
    ):
        """Validate a new request and either save its proposal or reserve beds."""
        student_ids = _student_ids(students)
        if type(allow_partial) is not bool:
            raise ValidationError("The partial allocation choice must be a boolean.")
        if allow_partial and len(student_ids) == 1:
            raise ValidationError("Partial allocation is available only for groups.")
        if not isinstance(notes, str):
            raise ValidationError("Allocation notes must be text.")

        students, university, campus, building = _lock_allocation_context(student_ids, building.pk)
        strategies = AllocationRequest.AllocationStrategy
        can_process = {
            strategies.AUTOMATIC: AllocationPolicy.can_execute_automatic_allocation,
            strategies.RECOMMENDED: AllocationPolicy.can_prepare_recommended_allocation,
            strategies.MANUAL: AllocationPolicy.can_prepare_manual_allocation,
        }[strategy]
        if not AllocationPolicy.can_initiate_allocation(actor, building) or not can_process(
            actor, building
        ):
            raise PermissionDenied("You do not have permission to start this allocation.")

        _require_operational_building(university, campus, building)
        if building.allocation_strategy != strategy:
            label = AllocationRequest.AllocationStrategy(strategy).label
            raise ValidationError(f"This building does not use {str(label).lower()} allocation.")

        _validate_dates(**schedule, local_today=_campus_local_date(campus, timezone.now()))
        students_by_gender = _validate_members(
            students, campus, building, schedule["expected_check_in"], allow_partial
        )
        if strategy == strategies.MANUAL:
            beds = _prepare_manual_beds(
                building, selected_beds_by_student, students_by_gender, allow_partial
            )
        else:
            beds = _select_beds(building, students_by_gender, len(students), allow_partial)
        now = _local_write_time(campus, schedule["expected_check_in"])

        request_type = (
            AllocationRequest.RequestType.INDIVIDUAL
            if len(students) == 1
            else AllocationRequest.RequestType.GROUP
        )
        request = AssignmentService._save_workflow_request(
            AllocationRequest(
                request_type=request_type,
                source=AllocationRequest.Source.ADMINISTRATIVE,
                allocation_strategy=building.allocation_strategy,
                allow_partial=allow_partial,
                building=building,
                requested_by=actor,
                notes=notes.strip(),
                **schedule,
            )
        )
        members = [
            AssignmentService._save_workflow_request(
                AllocationRequestMember(allocation_request=request, student=student)
            )
            for student in students
        ]

        if strategy != strategies.AUTOMATIC:
            return _write_proposals(request, members, beds)

        return _finalize(request, members, beds, schedule, actor, now)

    @staticmethod
    def refresh_recommendation(*, actor, allocation_request) -> AllocationRequest:
        """Replace stale bed suggestions on the same request.

        The students, dates, and original strategy are carried forward.
        If no replacement fits, the current proposal stays available for
        review and the caller gets a conflict.
        """
        return AllocationService._revise_proposal(
            actor=actor,
            allocation_request=allocation_request,
            strategy=AllocationRequest.AllocationStrategy.RECOMMENDED,
        )

    @staticmethod
    def revise_manual_selection(
        *, actor, allocation_request, selected_beds_by_student,
    ) -> AllocationRequest:
        """Replace the selected beds while the request still awaits approval.

        The selected mapping replaces the entire proposal. Students, dates,
        and the original strategy stay with the request.
        """
        return AllocationService._revise_proposal(
            actor=actor,
            allocation_request=allocation_request,
            strategy=AllocationRequest.AllocationStrategy.MANUAL,
            selected_beds_by_student=selected_beds_by_student,
        )

    @staticmethod
    @transaction.atomic
    def _revise_proposal(
        *, actor, allocation_request, strategy, selected_beds_by_student=None,
    ) -> AllocationRequest:
        """Validate and replace an open proposal using its saved strategy."""
        request, members, students, university, campus, building, schedule = (
            _request_context(allocation_request.pk)
        )
        is_manual = strategy == AllocationRequest.AllocationStrategy.MANUAL
        can_prepare = (
            AllocationPolicy.can_prepare_manual_allocation
            if is_manual
            else AllocationPolicy.can_prepare_recommended_allocation
        )
        if not can_prepare(actor, building):
            raise PermissionDenied("You do not have permission to revise this proposal.")

        _require_open_proposal(request, strategy)
        _require_operational_building(university, campus, building)
        _validate_dates(**schedule, local_today=_campus_local_date(campus, timezone.now()))
        pending_members = _open_members(members)
        _proposal_state(pending_members)
        pending_student_ids = {member.student_id for member in pending_members}
        students = [student for student in students if student.pk in pending_student_ids]
        if not students:
            raise ConflictError("This request has no members left to allocate.")

        students_by_gender = _validate_members(
            students, campus, building, schedule["expected_check_in"], request.allow_partial,
            request_id=request.pk,
        )
        if is_manual:
            beds = _prepare_manual_beds(
                building, selected_beds_by_student, students_by_gender, request.allow_partial
            )
        else:
            beds = _select_beds(building, students_by_gender, len(students), request.allow_partial)
        request, members = _lock_workflow(request, members)
        _local_write_time(campus, schedule["expected_check_in"])
        return _write_proposals(request, members, beds)

    @staticmethod
    def confirm_recommendation(
        *, actor, allocation_request, expected_beds_by_student,
    ) -> list[Assignment]:
        """Reserve the exact proposal reviewed by a manager or Global Admin.

        expected_beds_by_student maps Student primary keys to Bed primary
        keys. Requiring the reviewed map catches a refresh that took place
        while the manager was looking at an older recommendation.
        """
        return AllocationService._approve_proposal(
            actor=actor,
            allocation_request=allocation_request,
            strategy=AllocationRequest.AllocationStrategy.RECOMMENDED,
            expected_beds_by_student=expected_beds_by_student,
        )

    @staticmethod
    def approve_manual_allocation(
        *, actor, allocation_request, expected_beds_by_student,
    ) -> list[Assignment]:
        """Approve and reserve the exact manual selection the manager reviewed.

        Pass the student-to-bed mapping shown at review time. If staff revise
        the selection before approval, the manager must review it again.
        """
        return AllocationService._approve_proposal(
            actor=actor,
            allocation_request=allocation_request,
            strategy=AllocationRequest.AllocationStrategy.MANUAL,
            expected_beds_by_student=expected_beds_by_student,
        )

    @staticmethod
    @transaction.atomic
    def _approve_proposal(
        *, actor, allocation_request, strategy, expected_beds_by_student,
    ) -> list[Assignment]:
        """Recheck the saved proposal under lock and create its reservations."""
        request, members, students, university, campus, building, schedule = (
            _request_context(allocation_request.pk)
        )
        can_confirm = (
            AllocationPolicy.can_confirm_manual_allocation
            if strategy == AllocationRequest.AllocationStrategy.MANUAL
            else AllocationPolicy.can_confirm_recommended_allocation
        )
        if not can_confirm(actor, building):
            raise PermissionDenied("You do not have permission to approve this proposal.")

        _require_open_proposal(request, strategy)
        _require_operational_building(university, campus, building)
        _validate_dates(**schedule, local_today=_campus_local_date(campus, timezone.now()))
        pending_members = _open_members(members)
        proposals = _proposal_state(pending_members)
        if proposals != expected_beds_by_student:
            raise ConflictError("The selected beds changed. Review the current proposal.")

        if not proposals:
            raise ConflictError("Prepare a bed proposal before requesting approval.")

        if len(proposals) != len(pending_members) and not request.allow_partial:
            raise ConflictError("This proposal must include a bed for every remaining member.")

        pending_student_ids = {member.student_id for member in pending_members}
        students = [student for student in students if student.pk in pending_student_ids]
        students_by_gender = _validate_members(
            students, campus, building, schedule["expected_check_in"], request.allow_partial,
            request_id=request.pk,
        )
        beds = _lock_proposed_beds(building, proposals, students_by_gender)
        request, members = _lock_workflow(request, members)

        now = _local_write_time(campus, schedule["expected_check_in"])
        return _finalize(request, members, beds, schedule, actor, now)

    @staticmethod
    def reject_allocation_request(*, actor, allocation_request, reason="") -> AllocationRequest:
        """Reject every unfinished member as a manager or Global Admin.

        For a partial request, earlier reservations remain in place and
        their members keep their allocated outcome.
        """
        return AllocationService._resolve_unfinished_members(
            actor=actor,
            request_id=allocation_request.pk,
            member_status=AllocationRequestMember.Status.REJECTED,
            reason=reason,
        )

    @staticmethod
    def cancel_allocation_request(*, actor, allocation_request, reason="") -> AllocationRequest:
        """Withdraw every unfinished member and close the request."""
        return AllocationService._resolve_unfinished_members(
            actor=actor,
            request_id=allocation_request.pk,
            member_status=AllocationRequestMember.Status.WITHDRAWN,
            reason=reason,
        )

    @staticmethod
    def withdraw_allocation_member(*, actor, allocation_member, reason="") -> AllocationRequest:
        """Withdraw one unfinished member while the rest of the group continues."""
        return AllocationService._resolve_unfinished_members(
            actor=actor,
            request_id=allocation_member.allocation_request_id,
            member_id=allocation_member.pk,
            member_status=AllocationRequestMember.Status.WITHDRAWN,
            reason=reason,
        )

    @staticmethod
    @transaction.atomic
    def _resolve_unfinished_members(
        *, actor, request_id, member_status, reason, member_id=None,
    ) -> AllocationRequest:
        """Resolve open members under the same locks used by proposal approval."""
        if not isinstance(reason, str):
            raise ValidationError("The reason must be text.")

        request, members, _, _, _, building, _ = _request_context(request_id)
        can_manage = AllocationPolicy.can_approve_allocation(actor, building)
        if member_status == AllocationRequestMember.Status.REJECTED:
            if not can_manage:
                raise PermissionDenied("You do not have permission to reject this request.")
        elif not can_manage and not (
            AllocationPolicy.can_initiate_allocation(actor, building)
            and request.requested_by_id == actor.pk
        ):
            raise PermissionDenied("You do not have permission to withdraw from this request.")

        if (
            request.source != AllocationRequest.Source.ADMINISTRATIVE
            or request.status not in (
                AllocationRequest.Status.PENDING,
                AllocationRequest.Status.AWAITING_CONFIRMATION,
                AllocationRequest.Status.PARTIALLY_ALLOCATED,
            )
        ):
            raise ConflictError("This request is closed to administrative changes.")

        request, members = _lock_workflow(request, members)
        unfinished = _open_members(members)
        if member_id is not None:
            unfinished = [member for member in unfinished if member.pk == member_id]
        if not unfinished:
            raise ConflictError("There are no matching unfinished members to resolve.")

        now = timezone.now()
        reason = reason.strip()
        for member in unfinished:
            # An unfinished member may have a suggested bed. Clearing that
            # suggestion has no effect on any existing Assignment.
            member.assigned_bed = None
            member.status = member_status
            member.reason = reason
            member.resolved_at = now
            AssignmentService._save_workflow_request(
                member, update_fields=["assigned_bed", "status", "reason", "resolved_at"]
            )

        return _save_request_outcome(request, members, actor, now)
