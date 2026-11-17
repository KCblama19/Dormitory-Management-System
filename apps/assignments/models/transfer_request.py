import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract models
from apps.core.abstract_models.timestamp_models import TimeStampModel


class TransferRequest(TimeStampModel):
    """
    Represents a controlled movement from an existing Assignment
    to another physical bed.

    A transfer never changes the original Assignment's bed.

    Instead:

        Source Assignment
              |
        TransferRequest
              |
        Destination Assignment

    The destination Assignment is created through the
    Assignment.transfer_request OneToOne relationship.

    The source Assignment remains CHECKED_IN until the
    transfer is successfully completed.

    Transfer classification is derived from the source and
    destination locations. No transfer_type field is required.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        CANCELLED = "CANCELLED", _("Cancelled")
        COMPLETED = "COMPLETED", _("Completed")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # =========================================================
    # TRANSFER RELATIONSHIPS
    # =========================================================

    source_assignment = models.ForeignKey(
        "assignment.Assignment",
        on_delete=models.PROTECT,
        related_name="transfer_requests",
        verbose_name=_("source assignment"),
        help_text=_(
            "The student's existing accommodation Assignment."
        ),
    )

    destination_bed = models.ForeignKey(
        "accommodation.Bed",
        on_delete=models.PROTECT,
        related_name="destination_transfer_requests",
        verbose_name=_("destination bed"),
        help_text=_(
            "The physical bed requested as the new accommodation."
        ),
    )

    # =========================================================
    # REQUEST DETAILS
    # =========================================================

    transfer_reason = models.TextField(
        verbose_name=_("transfer reason"),
        help_text=_(
            "Mandatory explanation for requesting the transfer."
        ),
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_accommodation_transfers",
        verbose_name=_("initiated by"),
    )

    requested_move_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("requested move date"),
        help_text=_(
            "Requested date for student-initiated same-building "
            "transfers. Optional for other transfer workflows."
        ),
    )

    approved_move_date = models.DateField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("approved move date"),
    )

    # =========================================================
    # TRANSFER STATUS
    # =========================================================

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("transfer status"),
    )

    # =========================================================
    # DECISION HISTORY
    # =========================================================

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="decided_accommodation_transfers",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("decided by"),
    )

    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("decision timestamp"),
    )

    # =========================================================
    # COMPLETION HISTORY
    # =========================================================

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_accommodation_transfers",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("completed by"),
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("completion timestamp"),
    )

    # =========================================================
    # CANCELLATION REQUEST
    # =========================================================

    cancellation_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_accommodation_transfer_cancellations",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation requested by"),
    )

    cancellation_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation request timestamp"),
    )

    # =========================================================
    # CANCELLATION EXECUTION
    # =========================================================

    cancellation_reason = models.TextField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation reason"),
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_accommodation_transfers",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancelled by"),
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation timestamp"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Transfer Request")
        verbose_name_plural = _("Transfer Requests")

        indexes = [
            models.Index(
                fields=["source_assignment", "status"],
                name="transfer_source_status_idx",
            ),
            models.Index(
                fields=["destination_bed", "status"],
                name="transfer_destination_status_idx",
            ),
        ]

        constraints = [
            # -------------------------------------------------
            # Valid transfer status.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=Q(
                    status__in=["RESERVED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED", "EXPIRED", "TERMINATED"]),
                name="transfer_request_status_valid",
            ),

            # -------------------------------------------------
            # Transfer reason cannot be empty.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=Q(transfer_reason__gt=""),
                name="transfer_reason_not_empty",
            ),

            # -------------------------------------------------
            # One unresolved transfer per source Assignment.
            # -------------------------------------------------
            models.UniqueConstraint(
                fields=["source_assignment"],
                condition=Q(
                    status__in=[
                        "PENDING",
                        "APPROVED",
                    ]
                ),
                name="one_unresolved_transfer_per_source",
            ),

            # -------------------------------------------------
            # One unresolved transfer per destination bed.
            # -------------------------------------------------
            models.UniqueConstraint(
                fields=["destination_bed"],
                condition=Q(
                    status__in=[
                        "PENDING",
                        "APPROVED",
                    ]
                ),
                name="one_unresolved_transfer_per_destination",
            ),

            # -------------------------------------------------
            # PENDING transfers must not have decision,
            # completion, or executed cancellation metadata.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="PENDING")
                    |
                    Q(
                        decided_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                    )
                ),
                name="transfer_pending_metadata_valid",
            ),

            # -------------------------------------------------
            # APPROVED transfers require a decision and
            # an approved move date.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="APPROVED")
                    |
                    Q(
                        decided_at__isnull=False,
                        approved_move_date__isnull=False,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        cancellation_reason__isnull=True,
                    )
                ),
                name="transfer_approved_metadata_valid",
            ),

            # -------------------------------------------------
            # REJECTED transfers require a decision.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="REJECTED")
                    |
                    Q(
                        decided_at__isnull=False,
                        approved_move_date__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        cancellation_reason__isnull=True,
                    )
                ),
                name="transfer_rejected_metadata_valid",
            ),

            # -------------------------------------------------
            # CANCELLED transfers require cancellation metadata.
            # Cancellation may occur before or after approval.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="CANCELLED")
                    |
                    (
                        Q(
                            cancelled_at__isnull=False,
                            completed_at__isnull=True,
                        )
                        &
                        Q(cancellation_reason__gt="")
                    )
                ),
                name="transfer_cancelled_metadata_valid",
            ),

            # -------------------------------------------------
            # COMPLETED transfers require approval and completion.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="COMPLETED")
                    |
                    Q(
                        decided_at__isnull=False,
                        approved_move_date__isnull=False,
                        completed_at__isnull=False,
                        cancelled_at__isnull=True,
                        cancellation_reason__isnull=True,
                    )
                ),
                name="transfer_completed_metadata_valid",
            ),
        ]

    def clean(self):
        """
        Validate TransferRequest-specific data.

        Cross-record checks involving the source Assignment,
        destination bed, building, campus, and student are
        performed by TransferService inside a transaction.
        """
        super().clean()

        if self.transfer_reason is not None:
            self.transfer_reason = self.transfer_reason.strip()

            if not self.transfer_reason:
                raise ValidationError({
                    "transfer_reason": _(
                        "A transfer reason is required."
                    )
                })

    def __str__(self):
        return (
            f"Transfer | "
            f"{self.source_assignment.student.student_id} | "
            f"{self.get_status_display()}"
        )