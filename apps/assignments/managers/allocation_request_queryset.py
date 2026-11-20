from django.db import models
from django.db.models import Q


class AllocationRequestQuerySet(models.QuerySet):
    """
    Provides reusable, chainable queries for AllocationRequest.

    These methods handle database filtering only. They do not
    perform authorization, allocation, or lifecycle transitions.
    """

    # ---------------------------------------------------------
    # STATUS FILTERS
    # ---------------------------------------------------------

    def pending(self):
        """Return requests awaiting initial processing."""
        return self.filter(
            status=self.model.Status.PENDING
        )

    def awaiting_confirmation(self):
        """Return requests requiring administrative confirmation."""
        return self.filter(
            status=self.model.Status.AWAITING_CONFIRMATION
        )

    def partially_allocated(self):
        """Return requests with a partial allocation outcome."""
        return self.filter(
            status=self.model.Status.PARTIALLY_ALLOCATED
        )

    def completed(self):
        """Return fully completed allocation requests."""
        return self.filter(
            status=self.model.Status.COMPLETED
        )

    def rejected(self):
        """Return rejected allocation requests."""
        return self.filter(
            status=self.model.Status.REJECTED
        )

    def cancelled(self):
        """Return cancelled allocation requests."""
        return self.filter(
            status=self.model.Status.CANCELLED
        )

    def unresolved(self):
        """Return requests that still have allocation work to resolve."""
        return self.filter(
            Q(
                status__in=(
                    self.model.Status.PENDING,
                    self.model.Status.AWAITING_CONFIRMATION,
                ),
            )
            | Q(
                status=self.model.Status.PARTIALLY_ALLOCATED,
                members__status__in=("PENDING", "AWAITING_CONFIRMATION"),
            )
        ).distinct()

    # ---------------------------------------------------------
    # RELATIONSHIP FILTERS
    # ---------------------------------------------------------

    def for_building(self, building):
        """Return requests belonging to a specific building."""
        return self.filter(
            building=building
        )

    def requested_by(self, user):
        """Return requests initiated by a particular user."""
        return self.filter(
            requested_by=user
        )

    def for_student(self, student):
        """Return requests containing a particular student."""
        return self.filter(
            members__student=student
        ).distinct()

    # ---------------------------------------------------------
    # QUERY OPTIMIZATION
    # ---------------------------------------------------------

    def with_members(self):
        """Prefetch allocation members to avoid repeated queries."""
        return self.prefetch_related(
            "members"
        )

    def recent(self):
        """Return requests ordered from newest to oldest."""
        return self.order_by(
            "-created_at",
            "-pk",
        )