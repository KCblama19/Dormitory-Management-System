from django.contrib import admin

from apps.assignments.models import (
    AllocationRequest,
    AllocationRequestMember,
    Assignment,
    AssignmentExtension,
    CheckoutRequest,
    TransferRequest,
)
from apps.core.policies.base import BasePolicy


class ReadOnlyAssignmentAdmin(admin.ModelAdmin):
    """Let Global Admins inspect accommodation records in Django admin.

    Allocation and lifecycle changes belong in the services that enforce
    permissions, acquire locks, and record each transition.
    """

    actions = None

    def has_view_permission(self, request, obj=None):
        return (
            BasePolicy.is_global_admin(request.user)
            and super().has_view_permission(request, obj)
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AllocationRequest)
class AllocationRequestAdmin(ReadOnlyAssignmentAdmin):
    list_display = (
        "id",
        "building",
        "request_type",
        "allocation_strategy",
        "status",
        "created_at",
    )
    list_filter = ("status", "allocation_strategy", "request_type")
    list_select_related = ("building",)


@admin.register(AllocationRequestMember)
class AllocationRequestMemberAdmin(ReadOnlyAssignmentAdmin):
    list_display = ("id", "allocation_request_id", "student_id", "status", "resolved_at")
    list_filter = ("status",)
    search_fields = ("student__student_id",)


@admin.register(Assignment)
class AssignmentAdmin(ReadOnlyAssignmentAdmin):
    list_display = (
        "id",
        "student_id",
        "bed_id",
        "status",
        "review_status",
        "expected_check_in",
        "check_in_deadline",
    )
    list_filter = ("status", "review_status")
    search_fields = ("student__student_id",)
    date_hierarchy = "reserved_at"


@admin.register(AssignmentExtension, CheckoutRequest, TransferRequest)
class AssignmentWorkflowAdmin(ReadOnlyAssignmentAdmin):
    list_display = ("id", "status")
    list_filter = ("status",)