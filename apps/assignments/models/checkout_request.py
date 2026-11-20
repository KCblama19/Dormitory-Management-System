from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.core.abstract_models.timestamp_models import TimeStampModel


class CheckoutRequest(TimeStampModel):
    """A student's request to check out of an occupied assignment."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")

    assignment = models.ForeignKey(
        "assignments.Assignment",
        on_delete=models.PROTECT,
        related_name="checkout_requests",
    )
    requested_checkout_date = models.DateField(_("Requested checkout date"))
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkout_request_decisions",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    departure_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When physical departure was confirmed for this checkout."),
    )
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment"],
                condition=Q(status="PENDING"),
                name="assignment_one_pending_checkout",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="PENDING",
                        decided_by__isnull=True,
                        decided_at__isnull=True,
                        departure_verified_at__isnull=True,
                        decision_note="",
                    )
                    | Q(
                        status="REJECTED",
                        decided_by__isnull=False,
                        decided_at__isnull=False,
                        departure_verified_at__isnull=True,
                    )
                    | Q(
                        status="APPROVED",
                        decided_by__isnull=False,
                        decided_at__isnull=False,
                        departure_verified_at__isnull=False,
                        departure_verified_at__lte=F("decided_at"),
                    )
                ),
                name="assignment_checkout_decision_valid",
            ),
        ]

    def __str__(self):
        return f"Checkout for assignment {self.assignment_id} ({self.status})"