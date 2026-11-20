from django.shortcuts import redirect
from django import forms
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property


from apps.accommodations.models import Bed, Building
from apps.assignments.forms import (
    AllocationStudentsForm,
    AutomaticGroupAllocationForm,
    GroupAllocationOptionsForm,
    ManualAllocationFormSet,
    AllocationProposalApprovalForm,
    ManualAllocationRevisionForm,
    AllocationResolutionForm,
)
from apps.assignments.services.allocation_service import AllocationService
from apps.assignments.views.views import AssignmentServiceFormView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.views.generic import DetailView, ListView

from apps.assignments.models import AllocationRequest, AllocationRequestMember
from apps.core.policies.allocation_policy import AllocationPolicy


class AllocationRequestAccessMixin:
    """Scope allocation queries to buildings the signed-in user can view."""

    def get_queryset(self):
        actor = self.request.user
        requests = AllocationRequest.objects.select_related(
            "building",
            "requested_by",
            "decided_by",
        )

        if AllocationPolicy.is_global_admin(actor):
            return requests

        building = AllocationPolicy.managed_building(actor)
        if building is None or not AllocationPolicy.can_view_allocation_requests(
            actor,
            building,
        ):
            raise PermissionDenied(
                "You do not have permission to view allocation requests."
            )

        # Apply the building scope before resolving a request from its URL.
        return requests.filter(building_id=building.pk)


class AllocationRequestListView(
    LoginRequiredMixin,
    AllocationRequestAccessMixin,
    ListView,
):
    """Show unfinished allocation requests first, with access to history."""

    template_name = "assignments/allocation_request_list.html"
    context_object_name = "allocation_requests"
    paginate_by = 25

    def get_queryset(self):
        requests = super().get_queryset()

        if not self.show_history:
            # A partially allocated request stays in the queue as long as
            # it has a member whose outcome is still unfinished.
            requests = requests.unresolved()

        return requests.order_by("-created_at", "-pk")

    @property
    def show_history(self):
        """Return whether the user is viewing all requests in their scope."""
        return self.request.GET.get("scope") == "all"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_history"] = self.show_history
        return context


class AllocationRequestDetailView(
    LoginRequiredMixin,
    AllocationRequestAccessMixin,
    DetailView,
):
    """Show the request, its members, their bed selections, and outcomes."""

    template_name = "assignments/allocation_request_detail.html"
    context_object_name = "allocation_request"
    pk_url_kwarg = "request_id"

    def get_queryset(self):
        members = AllocationRequestMember.objects.select_related(
            "student",
            "assigned_bed__room__floor__building",
            "assignment",
        ).order_by("created_at", "pk")

        return super().get_queryset().prefetch_related(
            Prefetch("members", queryset=members),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["members"] = self.object.members.all()
        return context
    
class AllocationPreparationView(LoginRequiredMixin, AssignmentServiceFormView):
    """Prepare an allocation within the actor's building scope."""

    form_class = AllocationStudentsForm

    def get_buildings(self):
        actor = self.request.user
        buildings = Building.objects.filter(
            is_active=True,
            allocation_strategy=self.strategy,
        )

        if AllocationPolicy.is_global_admin(actor):
            return buildings

        building = AllocationPolicy.managed_building(actor)
        if building is None or not self.preparation_policy(actor, building):
            raise PermissionDenied(
                "You do not have permission to prepare this allocation."
            )

        return buildings.filter(pk=building.pk)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["buildings"] = self.get_buildings()
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data.copy()
        data["students"] = list(data["students"])
        return self.save_allocation(form, data)

    def save_allocation(self, form, data):
        """Pass validated inputs to the service that owns the workflow."""
        building = data.pop("building_id")

        return self.run_service(
            self.operation,
            form,
            on_success=self.redirect_to_allocation_request,
            actor=self.request.user,
            building=building,
            **data,
        )

    def redirect_to_allocation_request(self, allocation_request):
        return redirect(
            "assignments:allocation-request-detail",
            request_id=allocation_request.pk,
        )


class AutomaticGroupAllocationView(AllocationPreparationView):
    """Allocate an entire group, or the agreed subset, through the service."""

    form_class = AutomaticGroupAllocationForm
    template_name = "assignments/automatic_group_allocation_form.html"
    strategy = AllocationRequest.AllocationStrategy.AUTOMATIC
    preparation_policy = staticmethod(
        AllocationPolicy.can_execute_automatic_allocation
    )
    operation = staticmethod(
        AllocationService.execute_automatic_group_allocation
    )

    def redirect_to_allocation_request(self, reservations):
        # A successful automatic group allocation returns at least one
        # reservation. Every reservation points to the same group request.
        allocation_request = reservations[0].allocation_member.allocation_request
        return super().redirect_to_allocation_request(allocation_request)


class RecommendedAllocationPreparationView(AllocationPreparationView):
    """Generate recommendations for an individual student or a group."""

    template_name = "assignments/recommended_allocation_form.html"
    strategy = AllocationRequest.AllocationStrategy.RECOMMENDED
    preparation_policy = staticmethod(
        AllocationPolicy.can_prepare_recommended_allocation
    )
    operation = staticmethod(AllocationService.generate_recommendations)


class ManualAllocationPreparationView(AllocationPreparationView):
    """Save staff-selected beds for manager review."""

    form_class = GroupAllocationOptionsForm
    template_name = "assignments/manual_allocation_form.html"
    strategy = AllocationRequest.AllocationStrategy.MANUAL
    preparation_policy = staticmethod(
        AllocationPolicy.can_prepare_manual_allocation
    )
    operation = staticmethod(AllocationService.prepare_manual_allocation)

    def get_selection_formset(self, building=None):
        beds = Bed.objects.select_related("room__floor__building").filter(
            room__floor__building__in=self.get_buildings(),
        )

        if building is not None:
            beds = beds.filter(room__floor__building_id=building.pk)

        return ManualAllocationFormSet(
            data=self.request.POST if self.request.method == "POST" else None,
            prefix="selections",
            form_kwargs={"beds": beds},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self, "selection_formset"):
            self.selection_formset = self.get_selection_formset()

        context["selection_formset"] = self.selection_formset
        return context

    def form_valid(self, form):
        data = form.cleaned_data.copy()
        self.selection_formset = self.get_selection_formset(
            building=data["building_id"],
        )

        if not self.selection_formset.is_valid():
            return self.form_invalid(form)

        students = []
        selected_beds = {}

        for row in self.selection_formset.forms:
            if not row.cleaned_data:
                continue

            student = row.cleaned_data["student"]
            bed = row.cleaned_data["bed"]
            students.append(student)

            if bed is not None:
                selected_beds[student.pk] = bed.pk

        # Pass every student, including those whose rows have no bed.
        # The service checks consent and keeps those members pending.
        data["students"] = students
        data["selected_beds_by_student"] = selected_beds
        return self.save_allocation(form, data)
    
class AllocationRequestActionView(
    LoginRequiredMixin,
    AllocationRequestAccessMixin,
    AssignmentServiceFormView,
):
    """Load a scoped allocation request before running a form action."""

    def get_action_queryset(self):
        return self.get_queryset()

    @cached_property
    def allocation_request(self):
        allocation_request = get_object_or_404(
            self.get_action_queryset(),
            pk=self.kwargs["request_id"],
        )

        if not self.can_act_on_request(self.request.user, allocation_request):
            raise PermissionDenied(
                "You do not have permission to perform this allocation action."
            )

        return allocation_request

    def can_act_on_request(self, actor, allocation_request):
        return self.action_policy(actor, allocation_request.building)

    def get_form_kwargs(self):
        # Resolve permission before displaying or binding the form.
        _ = self.allocation_request
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allocation_request"] = self.allocation_request
        return context

    def get_service_target(self):
        return {"allocation_request": self.allocation_request}

    def save_request_action(self, form, **kwargs):
        return self.run_service(
            self.operation,
            form,
            on_success=self.redirect_to_request,
            actor=self.request.user,
            **self.get_service_target(),
            **kwargs,
        )

    def redirect_to_request(self, _result):
        return redirect(
            "assignments:allocation-request-detail",
            request_id=self.allocation_request.pk,
        )


class AllocationProposalActionView(AllocationRequestActionView):
    """Restrict proposal actions to the request's saved strategy."""

    def get_action_queryset(self):
        return super().get_action_queryset().filter(
            allocation_strategy=self.strategy,
        )


class RecommendedAllocationRefreshView(AllocationProposalActionView):
    """Regenerate suggested beds for the current recommended request."""

    form_class = forms.Form
    template_name = "assignments/refresh_allocation_recommendation_form.html"
    strategy = AllocationRequest.AllocationStrategy.RECOMMENDED
    action_policy = staticmethod(
        AllocationPolicy.can_prepare_recommended_allocation
    )
    operation = staticmethod(AllocationService.refresh_recommendation)

    def form_valid(self, form):
        return self.save_request_action(form)


class ManualAllocationRevisionView(AllocationProposalActionView):
    """Let staff revise a manual proposal before manager approval."""

    form_class = ManualAllocationRevisionForm
    template_name = "assignments/revise_manual_allocation_form.html"
    strategy = AllocationRequest.AllocationStrategy.MANUAL
    action_policy = staticmethod(AllocationPolicy.can_prepare_manual_allocation)
    operation = staticmethod(AllocationService.revise_manual_selection)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        allocation_request = self.allocation_request

        kwargs["members"] = list(
            allocation_request.members.unresolved()
            .select_related("student")
            .order_by("created_at", "pk")
        )
        kwargs["beds"] = Bed.objects.filter(
            room__floor__building_id=allocation_request.building_id,
        ).select_related("room__floor__building")

        return kwargs

    def form_valid(self, form):
        return self.save_request_action(
            form,
            selected_beds_by_student=form.selected_beds_by_student(),
        )


class AllocationProposalApprovalView(AllocationProposalActionView):
    """Send the selections the manager reviewed to the approval service."""

    form_class = AllocationProposalApprovalForm
    template_name = "assignments/approve_allocation_proposal_form.html"

    @cached_property
    def reviewed_members(self):
        return list(
            self.allocation_request.members.awaiting_confirmation()
            .filter(assigned_bed__isnull=False)
            .select_related("student", "assigned_bed__room__floor__building")
            .order_by("created_at", "pk")
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["allocation_request"] = self.allocation_request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if self.request.method == "GET":
            # Sign the same selections that are displayed in the template.
            initial["snapshot"] = self.form_class.make_snapshot(
                self.allocation_request,
                self.reviewed_members,
            )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reviewed_members"] = self.reviewed_members
        return context

    def form_valid(self, form):
        return self.save_request_action(
            form,
            expected_beds_by_student=form.cleaned_data["snapshot"],
        )


class RecommendedAllocationConfirmationView(AllocationProposalApprovalView):
    """Confirm the reviewed bed suggestions and create the reservations."""

    strategy = AllocationRequest.AllocationStrategy.RECOMMENDED
    action_policy = staticmethod(
        AllocationPolicy.can_confirm_recommended_allocation
    )
    operation = staticmethod(AllocationService.confirm_recommendation)


class ManualAllocationApprovalView(AllocationProposalApprovalView):
    """Approve the reviewed staff selections and create the reservations."""

    strategy = AllocationRequest.AllocationStrategy.MANUAL
    action_policy = staticmethod(AllocationPolicy.can_confirm_manual_allocation)
    operation = staticmethod(AllocationService.approve_manual_allocation)
    
class AllocationResolutionView(AllocationRequestActionView):
    """Resolve an administrative request that still has unfinished work."""

    form_class = AllocationResolutionForm

    def get_action_queryset(self):
        return super().get_action_queryset().unresolved().filter(
            source=AllocationRequest.Source.ADMINISTRATIVE,
        )

    def form_valid(self, form):
        return self.save_request_action(
            form,
            reason=form.cleaned_data["reason"],
        )


class AllocationRequestRejectView(AllocationResolutionView):
    """Let a scoped manager or Global Admin reject unfinished members."""

    template_name = "assignments/reject_allocation_request_form.html"
    action_policy = staticmethod(AllocationPolicy.can_approve_allocation)
    operation = staticmethod(AllocationService.reject_allocation_request)


class AllocationRequestCancelView(AllocationResolutionView):
    """Let an authorized user cancel the unfinished part of a request."""

    template_name = "assignments/cancel_allocation_request_form.html"
    operation = staticmethod(AllocationService.cancel_allocation_request)

    def can_act_on_request(self, actor, allocation_request):
        building = allocation_request.building

        # The original requester can cancel while they still have
        # permission to initiate allocations in this building.
        return AllocationPolicy.can_approve_allocation(actor, building) or (
            allocation_request.requested_by_id == actor.pk
            and AllocationPolicy.can_initiate_allocation(actor, building)
        )


class AllocationMemberWithdrawView(AllocationRequestCancelView):
    """Withdraw one unfinished member and preserve the rest of the request."""

    template_name = "assignments/withdraw_allocation_member_form.html"
    operation = staticmethod(AllocationService.withdraw_allocation_member)

    @cached_property
    def allocation_member(self):
        # Resolve the member through its parent request so another request's
        # member ID cannot be used under this URL.
        return get_object_or_404(
            self.allocation_request.members.unresolved().select_related("student"),
            pk=self.kwargs["member_id"],
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        _ = self.allocation_member
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allocation_member"] = self.allocation_member
        return context

    def get_service_target(self):
        return {"allocation_member": self.allocation_member}