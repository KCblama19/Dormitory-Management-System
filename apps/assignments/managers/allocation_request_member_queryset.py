from django.db import models



class AllocationRequestMemberQuerySet(models.QuerySet):
    """
    Provides reusable, chainable queries for allocation members.

    Individual member outcomes are independent of the overall
    AllocationRequest status.
    """

    # ---------------------------------------------------------
    # STATUS FILTERS
    # ---------------------------------------------------------

    def pending(self):
        """Return members awaiting initial processing."""
        return self.filter(
            status=self.model.Status.PENDING
        )

    def awaiting_confirmation(self):
        """Return members awaiting administrative confirmation."""
        return self.filter(
            status=self.model.Status.AWAITING_CONFIRMATION
        )

    def allocated(self):
        """Return successfully allocated members."""
        return self.filter(
            status=self.model.Status.ALLOCATED
        )

    def rejected(self):
        """Return rejected members."""
        return self.filter(
            status=self.model.Status.REJECTED
        )

    def withdrawn(self):
        """Return withdrawn members."""
        return self.filter(
            status=self.model.Status.WITHDRAWN
        )

    def unresolved(self):
        """Return members whose allocation outcome is not final."""
        return self.filter(
            status__in=self.model.UNRESOLVED_STATUSES
        )

    def resolved(self):
        """Return members whose allocation outcome is final."""
        return self.filter(
            status__in=self.model.RESOLVED_STATUSES
        )

    # ---------------------------------------------------------
    # RELATIONSHIP FILTERS
    # ---------------------------------------------------------

    def for_student(self, student):
        """Return allocation records belonging to a student."""
        return self.filter(
            student=student
        )

    def for_request(self, request):
        """Return members belonging to a specific request."""
        return self.filter(
            allocation_request=request
        )

    # ---------------------------------------------------------
    # QUERY OPTIMIZATION
    # ---------------------------------------------------------

    def with_related_data(self):
        """
        Retrieve related objects in the same query.

        Useful when displaying allocation members alongside
        their student, request, building, and selected bed.
        """
        return self.select_related(
            "student",
            "allocation_request",
            "allocation_request__building",
            "assigned_bed",
        )

    def recent(self):
        """Return members ordered from newest to oldest."""
        return self.order_by(
            "-created_at",
            "-pk",
        )
