import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.core.abstract_models.timestamp_models import TimeStampModel

# QuerySets
from apps.assignments.managers.allocation_request_member_queryset import (
    AllocationRequestMemberQuerySet
)

class AllocationRequestMember(TimeStampModel):
    """
    Represents an individual student participating in an
    accommodation AllocationRequest.

    An AllocationRequest can contain:

        INDIVIDUAL:
            Exactly one AllocationRequestMember.

        GROUP:
            Multiple AllocationRequestMember records.

    Each member has an independent allocation outcome.

    Allocation lifecycle:

        PENDING
            |
            +----> AWAITING_CONFIRMATION
            |             |
            |             +----> ALLOCATED
            |             +----> REJECTED
            |
            +----> ALLOCATED
            +----> REJECTED
            +----> WITHDRAWN

    ALLOCATED means the student has received an Assignment.

    Assignment owns the OneToOne relationship to this model.
    The reverse relationship is available through:

        member.assignment

    assigned_bed:
        Stores the proposed or selected physical bed.

        Once allocation succeeds, this must match the Bed
        referenced by the resulting Assignment.

    resolved_at:
        Remains NULL while the member is unresolved.
        Is populated when the member reaches a resolved state.

    Student-level unresolved allocation uniqueness is enforced
    through a conditional database constraint.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")

        AWAITING_CONFIRMATION = (
            "AWAITING_CONFIRMATION",
            _("Awaiting confirmation"),
        )

        ALLOCATED = "ALLOCATED", _("Allocated")
        REJECTED = "REJECTED", _("Rejected")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")

    UNRESOLVED_STATUSES = (
        Status.PENDING,
        Status.AWAITING_CONFIRMATION,
    )

    RESOLVED_STATUSES = (
        Status.ALLOCATED,
        Status.REJECTED,
        Status.WITHDRAWN,
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    allocation_request = models.ForeignKey(
        "assignments.AllocationRequest",
        on_delete=models.PROTECT,
        related_name="members",
        verbose_name=_("allocation request"),
        help_text=_(
            "The allocation operation to which this student belongs."
        ),
    )

    student = models.ForeignKey(
        "profiles.Student",
        on_delete=models.PROTECT,
        related_name="allocation_memberships",
        verbose_name=_("student"),
        help_text=_(
            "The student participating in this allocation operation."
        ),
    )

    status = models.CharField(
        _("Member status"),
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_(
            "The individual allocation outcome for this student."
        ),
    )

    assigned_bed = models.ForeignKey(
        "accommodations.Bed",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="allocation_members",
        verbose_name=_("assigned bed"),
        help_text=_(
            "The proposed or selected physical bed for this student. "
            "After successful allocation, it must match the bed "
            "referenced by the resulting Assignment."
        ),
    )

    reason = models.TextField(
        _("reason"),
        blank=True,
        help_text=_(
            "Optional explanation for rejection, withdrawal, "
            "or another allocation outcome."
        ),
    )

    resolved_at = models.DateTimeField(
        _("resolution date"),
        null=True,
        blank=True,
        help_text=_(
            "The date and time this student's allocation outcome "
            "was resolved."
        ),
    )
    
    objects = AllocationRequestMemberQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]

        verbose_name = _("Allocation Request Member")
        verbose_name_plural = _("Allocation Request Members")

        constraints = [
            # A student can participate only once in the same request.
            models.UniqueConstraint(
                fields=["allocation_request", "student"],
                name="uniq_req_member_student",
            ),

            # A student cannot participate in multiple unresolved
            # allocation operations simultaneously.
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(
                    status__in=[
                        "PENDING",
                        "AWAITING_CONFIRMATION",
                    ]
                ),
                name="uniq_unresolved_alloc_student",
            ),

            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "PENDING",
                        "AWAITING_CONFIRMATION",
                        "ALLOCATED",
                        "REJECTED",
                        "WITHDRAWN",
                    ]
                ),
                name="allocation_member_status_valid",
            ),

            # Unresolved members must not have a resolution timestamp.
            # Resolved members must have one.
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[
                            "PENDING",
                            "AWAITING_CONFIRMATION",
                        ],
                        resolved_at__isnull=True,
                    )
                    | Q(
                        status__in=[
                            "ALLOCATED",
                            "REJECTED",
                            "WITHDRAWN",
                        ],
                        resolved_at__isnull=False,
                    )
                ),
                name="allocation_member_resolution_valid",
            ),

            # A successfully allocated member must identify a bed.
            models.CheckConstraint(
                condition=(
                    ~Q(status="ALLOCATED")
                    | Q(assigned_bed__isnull=False)
                ),
                name="allocation_member_allocated_bed",
            ),
        ]

        indexes = [
            models.Index(
                fields=["allocation_request", "status"],
                name="alloc_member_req_status_id",
            ),
            models.Index(
                fields=["student", "status"],
                name="alloc_member_student_status_id",
            ),
        ]

    def clean(self):
        """
        Validate member-specific lifecycle rules.

        Cross-model validation involving the resulting Assignment
        is enforced by the allocation services.
        """
        super().clean()

        if (
            self.status in self.UNRESOLVED_STATUSES
            and self.resolved_at is not None
        ):
            raise ValidationError({
                "resolved_at": _(
                    "An unresolved allocation member cannot "
                    "have a resolution timestamp."
                )
            })

        if (
            self.status in self.RESOLVED_STATUSES
            and self.resolved_at is None
        ):
            raise ValidationError({
                "resolved_at": _(
                    "A resolved allocation member must have "
                    "a resolution timestamp."
                )
            })

        if (
            self.status == self.Status.ALLOCATED
            and not self.assigned_bed_id
        ):
            raise ValidationError({
                "assigned_bed": _(
                    "An allocated member must have an assigned bed."
                )
            })

    def __str__(self):
        return (
            f"{self.student.student_id} | "
            f"{self.get_status_display()}"
        )
