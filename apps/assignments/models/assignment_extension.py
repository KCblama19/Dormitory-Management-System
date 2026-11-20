from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.abstract_models.timestamp_models import TimeStampModel


class AssignmentExtension(TimeStampModel):
    """A student's request to extend the check-in deadline for a reservation."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")

    assignment = models.ForeignKey(
        "assignments.Assignment",
        on_delete=models.PROTECT,
        related_name="extensions",
    )
    requested_check_in_deadline = models.DateField(
        _("Requested check-in deadline"),
        help_text=_("The proposed deadline date before grace days are added."),
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignment_extension_decisions",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment"],
                condition=Q(status="PENDING"),
                name="assignment_one_pending_extension",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="PENDING",
                        decided_by__isnull=True,
                        decided_at__isnull=True,
                        decision_note="",
                    )
                    | Q(
                        status__in=["APPROVED", "REJECTED"],
                        decided_by__isnull=False,
                        decided_at__isnull=False,
                    )
                ),
                name="assignment_extension_decision_valid",
            ),
        ]

    def __str__(self):
        return f"Extension for assignment {self.assignment_id} ({self.status})"