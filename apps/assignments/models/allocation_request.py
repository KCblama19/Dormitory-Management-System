
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.core.abstract_models.timestamp_models import TimeStampModel

# QuerySets
from apps.assignments.managers.allocation_request_queryset import (
    AllocationRequestQuerySet
)


class AllocationRequest(TimeStampModel):
    """
    Represents an individual or group accommodation allocation operation.

    An AllocationRequest is the parent record for one or more
    AllocationRequestMember records.

    Allocation strategies:
        AUTOMATIC:
            Allocate and reserve suitable beds immediately.

        RECOMMENDED:
            Generate recommended bed selections without reserving them.
            Staff must confirm the selections before assignments are created.

        MANUAL:
            Allow authorized staff to select beds manually.
            Assignments are created only after confirmation and revalidation.

    Request origins:
        ADMINISTRATIVE:
            An allocation initiated by an administrator or authorized
            accommodation administrator.
            
            Could be: 
                [
                    Global Admin, 
                    Building Manager, 
                    Building Staff
                ]

        BOOKING:
            Reserved for future integration with the Booking module.
            Booking-originated requests are not supported yet.

    Important:
        The selected allocation strategy is stored on this record.
        It must not change when the Building's allocation configuration
        changes later.

    Request/member status consistency is enforced transactionally
    by the allocation services because it depends on multiple records.
    """

    class RequestType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", _("Individual")
        GROUP = "GROUP", _("Group")

    class Source(models.TextChoices):
        BOOKING = "BOOKING", _("Booking")
        ADMINISTRATIVE = "ADMINISTRATIVE", _("Administrative")

    class AllocationStrategy(models.TextChoices):
        AUTOMATIC = "AUTOMATIC", _("Automatic")
        RECOMMENDED = "RECOMMENDED", _("Recommended")
        MANUAL = "MANUAL", _("Manual")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        AWAITING_CONFIRMATION = (
            "AWAITING_CONFIRMATION",
            _("Awaiting confirmation"),
        )
        PARTIALLY_ALLOCATED = (
            "PARTIALLY_ALLOCATED",
            _("Partially allocated"),
        )
        COMPLETED = "COMPLETED", _("Completed")
        REJECTED = "REJECTED", _("Rejected")
        CANCELLED = "CANCELLED", _("Cancelled")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    request_type = models.CharField(
        _("Request type"),
        max_length=20,
        choices=RequestType.choices,
        help_text=_(
            "Determines whether this allocation operation "
            "involves one student or a group of students."
        ),
    )

    source = models.CharField(
        _("Request source"),
        max_length=20,
        choices=Source.choices,
        default=Source.ADMINISTRATIVE,
        help_text=_(
            "Identifies whether this allocation originated from "
            "an administrative operation or a Booking request."
        ),
    )

    allocation_strategy = models.CharField(
        _("Allocation strategy"),
        max_length=20,
        choices=AllocationStrategy.choices,
        help_text=_(
            "The allocation strategy selected for this operation. "
            "This value is a snapshot and remains unchanged if "
            "the Building's allocation configuration changes."
        ),
    )
    
    allow_partial = models.BooleanField(
        _("Allow partial allocation"),
        default=False,
        help_text=_(
            "The initiating staff member confirmed that the group accepts "
            "an allocation that reserves beds for only some of its members."
        ),
    )
    

    building = models.ForeignKey(
        "accommodation.Building",
        on_delete=models.PROTECT,
        related_name="allocation_requests",
        verbose_name=_("building"),
        help_text=_(
            "The building in which students are being allocated."
        ),
    )

    status = models.CharField(
        _("Request status"),
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_(
            "The current overall state of the allocation operation."
        ),
    )
    
    expected_check_in = models.DateField(
        _("Expected check-in"),
        null=True,
        blank=True,
    )

    expected_check_out = models.DateField(
        _("Expected checkout"),
        null=True,
        blank=True,
    )

    check_in_deadline = models.DateField(
        _("Check-in deadline"),
        null=True,
        blank=True,
    )

    grace_period_days = models.PositiveIntegerField(
        _("Grace period days"),
        default=0,
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocation_requests_created",
        verbose_name=_("requested by"),
        help_text=_(
            "The user who initiated this allocation operation. "
            "The reference is cleared if that user account is deleted."
        ),
    )

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocation_requests_decided",
        verbose_name=_("decided by"),
        help_text=_(
            "The user responsible for the final administrative "
            "decision, when applicable."
        ),
    )

    decided_at = models.DateTimeField(
        _("decision date"),
        null=True,
        blank=True,
    )

    notes = models.TextField(
        _("notes"),
        blank=True,
        help_text=_(
            "Optional administrative notes concerning this "
            "allocation operation."
        ),
    )
    
    objects = AllocationRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

        verbose_name = _("Allocation Request")
        verbose_name_plural = _("Allocation Requests")

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    request_type__in=[
                        "INDIVIDUAL",
                        "GROUP",
                    ]
                ),
                name="allocation_req_type_valid",
            ),

            # Booking-originated allocations are intentionally
            # disabled until the Booking module is implemented.
            models.CheckConstraint(
                condition=Q(source="ADMINISTRATIVE"),
                name="allocation_req_source_admin",
            ),

            models.CheckConstraint(
                condition=Q(
                    allocation_strategy__in=[
                        "AUTOMATIC",
                        "RECOMMENDED",
                        "MANUAL",
                    ]
                ),
                name="allocation_req_strategy_valid",
            ),

            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "PENDING",
                        "AWAITING_CONFIRMATION",
                        "PARTIALLY_ALLOCATED",
                        "COMPLETED",
                        "REJECTED",
                        "CANCELLED",
                    ]
                ),
                name="allocation_req_status_valid",
            ),

            # A decision actor and decision timestamp must either
            # both exist or both remain empty.
            models.CheckConstraint(
                condition=(
                    Q(decided_by__isnull=True)
                    | Q(decided_at__isnull=False)
                ),
                name="allocation_req_decision_pair",
            ),

            models.CheckConstraint(
                condition=Q(allow_partial=False) | Q(request_type="GROUP"),
                name="allocation_partial_group_only",
            ),
        ]

        indexes = [
            models.Index(
                fields=["building", "status", "created_at"],
                name="alloc_req_build_status_idx",
            ),
            models.Index(
                fields=["requested_by", "status"],
                name="alloc_req_actor_status_idx",
            ),
        ]

    def clean(self):
        """
        Validate AllocationRequest-specific rules.

        Aggregate rules involving AllocationRequestMember records
        are deliberately handled by transactional services.
        """
        super().clean()

        if self.source == self.Source.BOOKING:
            raise ValidationError({
                "source": _(
                    "Booking-originated allocations are not supported "
                    "until the Booking module is implemented."
                )
            })

    def __str__(self):
        return (
            f"{self.get_request_type_display()} Allocation | "
            f"{self.building} | {self.get_status_display()}"
        )
