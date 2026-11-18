import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Abstract models
from apps.core.abstract_models.timestamp_models import TimeStampModel


class Assignment(TimeStampModel):
    """
    Represents the actual accommodation commitment between a student
    and a physical bed.

    An Assignment is created immediately after successful allocation.
    Its initial state is RESERVED, not CHECKED_IN.

    The Assignment preserves the complete accommodation lifecycle,
    including reservation, check-in, checkout, cancellation,
    expiration, and administrative termination.

    Origin relationships:

        Normal allocation:
            allocation_member is populated.
            transfer_request is NULL.

        Transfer allocation:
            allocation_member is NULL.
            transfer_request is populated.

    Exactly one origin must be populated.

    Important:
        Physical bed availability belongs to the Accommodation module.
        Logical reservation and occupancy belong to this model.
    """

    class Status(models.TextChoices):
        RESERVED = "RESERVED", _("Reserved")
        CHECKED_IN = "CHECKED_IN", _("Checked in")
        CHECKED_OUT = "CHECKED_OUT", _("Checked out")
        CANCELLED = "CANCELLED", _("Cancelled")
        EXPIRED = "EXPIRED", _("Expired")
        TERMINATED = "TERMINATED", _("Terminated")

    class ReviewStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", _("Not required")
        PENDING = "PENDING", _("Pending")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # =========================================================
    # CORE RELATIONSHIPS
    # =========================================================

    student = models.ForeignKey(
        "profiles.Student",
        on_delete=models.PROTECT,
        related_name="accommodation_assignments",
        verbose_name=_("student"),
        help_text=_(
            "The student receiving this accommodation assignment."
        ),
    )

    bed = models.ForeignKey(
        "accommodation.Bed",
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name=_("bed"),
        help_text=_(
            "The physical bed committed to this student."
        ),
    )

    allocation_member = models.OneToOneField(
        "assignment.AllocationRequestMember",
        on_delete=models.PROTECT,
        related_name="assignment",
        null=True,
        blank=True,
        verbose_name=_("allocation request member"),
        help_text=_(
            "The allocation request member responsible for "
            "creating this Assignment. NULL for transfer Assignments."
        ),
    )

    transfer_request = models.OneToOneField(
        "assignment.TransferRequest",
        on_delete=models.PROTECT,
        related_name="destination_assignment",
        null=True,
        blank=True,
        verbose_name=_("transfer request"),
        help_text=_(
            "The transfer request responsible for creating this "
            "Assignment. NULL for normal allocations."
        ),
    )

    # =========================================================
    # ASSIGNMENT LIFECYCLE
    # =========================================================

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RESERVED,
        verbose_name=_("assignment status"),
        help_text=_(
            "Current lifecycle state of this accommodation assignment."
        ),
    )

    expected_check_in = models.DateField(
        verbose_name=_("expected check-in date"),
        help_text=_(
            "The expected calendar date of the student's arrival, "
            "interpreted using the Campus's timezone."
        ),
    )

    expected_check_out = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("expected check-out date"),
        help_text=_(
            "Optional expected departure date. Reaching this date "
            "does not automatically release the bed."
        ),
    )

    check_in_deadline = models.DateField(
        verbose_name=_("check-in deadline"),
        help_text=_(
            help_text=_(
                "The base check-in deadline in the campus's local calendar. "
                "The grace period starts after this date."
            )
        ),
    )

    actual_check_in = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("actual check-in"),
    )

    actual_check_out = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("actual check-out"),
    )

    reserved_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name=_("reservation timestamp"),
    )

    # =========================================================
    # CANCELLATION HISTORY
    # =========================================================

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation timestamp"),
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_accommodation_assignments",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancelled by"),
    )

    cancellation_reason = models.TextField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("cancellation reason"),
    )

    # =========================================================
    # EXPIRATION HISTORY
    # =========================================================

    expired_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("expiration timestamp"),
    )

    overdue_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("overdue timestamp"),
        help_text=_(
            "Records when the expiration process first identified "
            "this reservation as overdue."
        ),
    )

    grace_period_days = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("grace period in days"),
        help_text=_(
            "Snapshot of the grace period applied when this "
            "Assignment was created. Later configuration changes "
            "must not modify this value."
        ),
    )

    # =========================================================
    # ADMINISTRATIVE TERMINATION
    # =========================================================

    terminated_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("termination timestamp"),
    )

    terminated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="terminated_accommodation_assignments",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("terminated by"),
    )

    termination_reason = models.TextField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("termination reason"),
    )

    # =========================================================
    # EARLY CHECK-IN
    # =========================================================

    early_check_in_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_early_accommodation_checkins",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("early check-in approved by"),
        help_text=_(
            "The authorized staff member who approved early check-in. "
            "NULL when early check-in approval was not required."
        ),
    )

    # =========================================================
    # ELIGIBILITY REVIEW
    # =========================================================

    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NOT_REQUIRED,
        verbose_name=_("eligibility review status"),
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_accommodation_assignments",
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("reviewed by"),
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("review timestamp"),
    )

    class Meta:
        ordering = ["-reserved_at"]
        verbose_name = _("Assignment")
        verbose_name_plural = _("Assignments")

        indexes = [
            models.Index(
                fields=["student", "status"],
                name="assignment_student_status_idx",
            ),
            models.Index(
                fields=["status", "check_in_deadline"],
                name="assignment_status_deadline_idx",
            ),
            models.Index(
                fields=["review_status", "status"],
                name="assignment_review_status_idx",
            ),
        ]

        constraints = [
            # -------------------------------------------------
            # One active Assignment per physical bed.
            # -------------------------------------------------
            models.UniqueConstraint(
                fields=["bed"],
                condition=Q(
                    status__in=[
                        "RESERVED",
                        "CHECKED_IN",
                    ]
                ),
                name="one_active_assignment_per_bed",
            ),

            # -------------------------------------------------
            # Exactly one origin must be populated.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    Q(
                        allocation_member__isnull=False,
                        transfer_request__isnull=True,
                    )
                    |
                    Q(
                        allocation_member__isnull=True,
                        transfer_request__isnull=False,
                    )
                ),
                name="assignment_origin_exactly_one",
            ),

            # -------------------------------------------------
            # Valid lifecycle status.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=Q(status__in=
                            ["RESERVED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED", "EXPIRED", "TERMINATED"]),
                name="assignment_status_valid",
            ),

            # -------------------------------------------------
            # Valid eligibility review status.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=Q(
                    review_status__in=[
                        "NOT_REQUIRED", 
                        "PENDING", 
                        "APPROVED", 
                        "REJECTED", 
                    ]
                ),
                name="assignment_review_status_valid",
            ),

            # -------------------------------------------------
            # Expected checkout must follow expected check-in.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    Q(expected_check_out__isnull=True)
                    |
                    Q(
                        expected_check_out__gt=F("expected_check_in")
                    )
                ),
                name="assignment_expected_checkout_after_checkin",
            ),

            # -------------------------------------------------
            # Actual checkout cannot precede actual check-in.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    Q(actual_check_out__isnull=True)
                    |
                    Q(
                        actual_check_in__isnull=False,
                        actual_check_out__gte=F("actual_check_in"),
                    )
                ),
                name="assignment_actual_checkout_valid",
            ),

            # -------------------------------------------------
            # Review metadata must agree with review status.
            #
            # reviewed_by may become NULL after account deletion.
            # reviewed_at remains the permanent decision timestamp.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    Q(
                        review_status__in=[
                            "NOT_REQUIRED",
                            "PENDING",
                        ],
                        reviewed_by__isnull=True,
                        reviewed_at__isnull=True,
                    )
                    |
                    Q(
                        review_status__in=[
                            "APPROVED",
                            "REJECTED",
                        ],
                        reviewed_at__isnull=False,
                    )
                ),
                name="assignment_review_metadata_consistent",
            ),

            # -------------------------------------------------
            # RESERVED state.
            # No check-in or terminal event may exist.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="RESERVED")
                    |
                    Q(
                        actual_check_in__isnull=True,
                        actual_check_out__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                        expired_at__isnull=True,
                        terminated_at__isnull=True,
                        terminated_by__isnull=True,
                        termination_reason__isnull=True,
                    )
                ),
                name="assignment_reserved_metadata_valid",
            ),

            # -------------------------------------------------
            # CHECKED_IN state.
            # Check-in exists, but checkout and terminal events
            # have not occurred.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="CHECKED_IN")
                    |
                    Q(
                        actual_check_in__isnull=False,
                        actual_check_out__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                        expired_at__isnull=True,
                        terminated_at__isnull=True,
                        terminated_by__isnull=True,
                        termination_reason__isnull=True,
                    )
                ),
                name="assignment_checked_in_metadata_valid",
            ),

            # -------------------------------------------------
            # CHECKED_OUT state.
            # Both actual timestamps must exist.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="CHECKED_OUT")
                    |
                    Q(
                        actual_check_in__isnull=False,
                        actual_check_out__isnull=False,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                        expired_at__isnull=True,
                        terminated_at__isnull=True,
                        terminated_by__isnull=True,
                        termination_reason__isnull=True,
                    )
                ),
                name="assignment_checked_out_metadata_valid",
            ),

            # -------------------------------------------------
            # CANCELLED state.
            # A reservation cannot be cancelled after check-in.
            # The actor FK may become NULL after account deletion.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="CANCELLED")
                    |
                    (
                        Q(
                            actual_check_in__isnull=True,
                            actual_check_out__isnull=True,
                            cancelled_at__isnull=False,
                            expired_at__isnull=True,
                            terminated_at__isnull=True,
                            terminated_by__isnull=True,
                            termination_reason__isnull=True,
                        )
                        &
                        Q(cancellation_reason__gt="")
                    )
                ),
                name="assignment_cancelled_metadata_valid",
            ),

            # -------------------------------------------------
            # EXPIRED state.
            # Expiration only applies to reservations that never
            # completed check-in.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="EXPIRED")
                    |
                    Q(
                        actual_check_in__isnull=True,
                        actual_check_out__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                        expired_at__isnull=False,
                        terminated_at__isnull=True,
                        terminated_by__isnull=True,
                        termination_reason__isnull=True,
                    )
                ),
                name="assignment_expired_metadata_valid",
            ),

            # -------------------------------------------------
            # TERMINATED state.
            # Termination applies to an Assignment that had
            # already completed check-in.
            # -------------------------------------------------
            models.CheckConstraint(
                condition=(
                    ~Q(status="TERMINATED")
                    |
                    (
                        Q(
                            actual_check_in__isnull=False,
                            actual_check_out__isnull=True,
                            cancelled_at__isnull=True,
                            cancelled_by__isnull=True,
                            cancellation_reason__isnull=True,
                            expired_at__isnull=True,
                            terminated_at__isnull=False,
                        )
                        &
                        Q(termination_reason__gt="")
                    )
                ),
                name="assignment_terminated_metadata_valid",
            ),
        ]

    # =========================================================
    # MODEL VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate Assignment-specific rules.

        Database constraints provide the final protection for
        rules that can be represented at the database level.

        Campus-timezone deadline calculations remain in the
        Assignment services because they require the related
        Campus timezone and calendar-day semantics.
        """
        super().clean()

        errors = {}

        if (
            self.expected_check_out
            and self.expected_check_in
            and self.expected_check_out <= self.expected_check_in
        ):
            errors["expected_check_out"] = _(
                "Expected check-out must be later than expected check-in."
            )

        if self.actual_check_out:
            if not self.actual_check_in:
                errors["actual_check_out"] = _(
                    "Actual check-in must exist before actual check-out."
                )
            elif self.actual_check_out < self.actual_check_in:
                errors["actual_check_out"] = _(
                    "Actual check-out cannot precede actual check-in."
                )

        if (
            settings.USE_TZ
            and self.check_in_deadline
        ):
            errors["check_in_deadline"] = _(
                "The check-in deadline must be timezone-aware."
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================
    # DISPLAY
    # =========================================================

    def __str__(self):
        return (
            f"{self.student.student_id} | "
            f"{self.bed} | "
            f"{self.get_status_display()}"
        )