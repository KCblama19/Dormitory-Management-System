from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, FormView, ListView

# MODELS
from apps.assignments.models import (
    Assignment,
    AssignmentExtension, 
    CheckoutRequest,
    TransferRequest,
)
from apps.accommodations.models import Building
from apps.assignments.models import Assignment

# ASSIGNMENT FORMS
from apps.assignments.forms import (
    AssignmentCheckInForm,
    AutomaticAllocationForm,
    ReservationCancellationForm,
    AssignmentExtensionRequestForm,
    CheckoutDecisionForm,
    CheckoutRequestForm,
    WorkflowDecisionForm,
    AssignmentEligibilityDecisionForm,
    AssignmentTerminationForm
)

# SERVICES
from apps.assignments.services.allocation_service import AllocationService
from apps.assignments.services.assignment_service import AssignmentService

# DJANGO EXCEPTIONS
from django.core.exceptions import ValidationError as DjangoValidationError

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)

# APPLICATION POLICIES
from apps.core.policies.allocation_policy import AllocationPolicy
from apps.core.policies.assignment_policy import AssignmentPolicy
from apps.core.policies.transfer_policy import TransferPolicy



class AssignmentServiceFormView(FormView):
    """Run a service operation and show its business errors on the form."""

    def run_service(self, operation, form, *, on_success, **kwargs):
        try:
            result = operation(**kwargs)
        except PermissionDenied as exc:
            raise DjangoPermissionDenied(str(exc)) from exc
        except NotFoundError as exc:
            raise Http404(str(exc)) from exc
        except (ConflictError, ValidationError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        return on_success(result)

    def save_assignment(self, operation, form, *, redirect_assignment_id=None, **kwargs):
        """Run an Assignment operation and return to its detail page."""

        def redirect_to_assignment(result):
            assignment_id = (
                result.pk if redirect_assignment_id is None else redirect_assignment_id
            )
            return redirect(
                "assignments:assignment-detail",
                assignment_id=assignment_id,
            )

        return self.run_service(
            operation,
            form,
            on_success=redirect_to_assignment,
            **kwargs,
        )
        
class AutomaticAllocationView(LoginRequiredMixin, AssignmentServiceFormView):
    """Allocate one student through the building's automatic workflow."""

    form_class = AutomaticAllocationForm
    template_name = "assignments/automatic_allocation_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        actor = self.request.user

        if AllocationPolicy.is_global_admin(actor):
            kwargs["buildings"] = Building.objects.all()
            return kwargs

        building = AllocationPolicy.managed_building(actor)
        if building is None or not AllocationPolicy.can_execute_automatic_allocation(
            actor, building
        ):
            raise DjangoPermissionDenied(
                "You do not have permission to allocate accommodation."
            )

        kwargs["buildings"] = Building.objects.filter(pk=building.pk)
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        return self.save_assignment(
            AllocationService.execute_automatic_allocation,
            form,
            actor=self.request.user,
            student=data["student_id"],
            building=data["building_id"],
            expected_check_in=data["expected_check_in"],
            check_in_deadline=data["check_in_deadline"],
            expected_check_out=data["expected_check_out"],
            grace_period_days=data["grace_period_days"],
            notes=data["notes"],
        )


class AssignmentAccessMixin:
    """Load an Assignment from the signed-in user's permitted scope."""

    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(
            assignments_visible_to(request.user),
            pk=kwargs["assignment_id"],
        )

        if not AssignmentPolicy.can_view_assignment(request.user, self.assignment):
            raise Http404("Assignment not found.")

        self.check_assignment_permission()
        return super().dispatch(request, *args, **kwargs)

    def check_assignment_permission(self):
        """Allow lifecycle views to require permission for a specific action."""
        
        
def assignments_visible_to(actor):
    """Return the Assignments this actor may find through the web views."""
    assignments = Assignment.objects.select_related(
        "student",
        "bed__room__floor__building",
    )

    if AssignmentPolicy.is_global_admin(actor):
        return assignments

    if AssignmentPolicy.is_student_account(actor):
        return assignments.filter(student__user_id=actor.pk)

    building = AssignmentPolicy.managed_building(actor)
    if building is not None and AssignmentPolicy.works_in_building(actor, building):
        return assignments.filter(bed__room__floor__building_id=building.pk)

    return assignments.none()

class AssignmentDetailView(LoginRequiredMixin, AssignmentAccessMixin, DetailView):
    """Show an Assignment, its pending requests, and the actor's actions."""

    model = Assignment
    template_name = "assignments/assignment_detail.html"
    context_object_name = "assignment"

    def get_object(self, queryset=None):
        return self.assignment

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor = self.request.user
        assignment = self.object
        building = assignment.bed.room.floor.building

        pending_extension = AssignmentExtension.objects.filter(
            assignment_id=assignment.pk,
            status="PENDING",
        ).first()
        pending_checkout = CheckoutRequest.objects.filter(
            assignment_id=assignment.pk,
            status="PENDING",
        ).first()

        open_transfers = TransferRequest.objects.filter(
            source_assignment_id=assignment.pk,
            status__in=(
                TransferRequest.Status.PENDING,
                TransferRequest.Status.APPROVED,
            ),
        ).select_related("destination_bed__room__floor__building")

        if not AssignmentPolicy.is_global_admin(actor):
            open_transfers = open_transfers.filter(
                destination_bed__room__floor__building_id=building.pk,
            )

        is_reserved = assignment.status == Assignment.Status.RESERVED
        is_checked_in = assignment.status == Assignment.Status.CHECKED_IN
        is_ordinary_reservation = is_reserved and assignment.transfer_request_id is None

        context.update(
            pending_extension=pending_extension,
            pending_checkout=pending_checkout,
            open_transfers=open_transfers,
            actions={
                "check_in": (
                    is_ordinary_reservation
                    and AssignmentPolicy.can_check_in(actor, assignment)
                ),
                "cancel_reservation": (
                    is_ordinary_reservation
                    and AssignmentPolicy.can_cancel_reservation(actor, assignment)
                ),
                "request_extension": (
                    is_reserved
                    and pending_extension is None
                    and AssignmentPolicy.can_request_extension(actor, assignment)
                ),
                "decide_extension": (
                    pending_extension is not None
                    and AssignmentPolicy.can_decide_extension(actor, pending_extension)
                ),
                "request_checkout": (
                    is_checked_in
                    and pending_checkout is None
                    and AssignmentPolicy.can_request_checkout(actor, assignment)
                ),
                "decide_checkout": (
                    pending_checkout is not None
                    and AssignmentPolicy.can_resolve_checkout_request(actor, pending_checkout)
                ),
                "request_transfer": (
                    is_checked_in
                    and TransferPolicy.can_request_transfer(
                        actor,
                        source=assignment,
                        destination_building=building,
                    )
                ),
                "decide_eligibility": (
                    (is_reserved or is_checked_in)
                    and assignment.review_status == Assignment.ReviewStatus.PENDING
                    and AssignmentPolicy.can_review_eligibility(actor, assignment)
                ),
                "terminate": (
                    is_checked_in
                    and AssignmentPolicy.can_terminate_assignment(actor, assignment)
                ),
            },
        )
        return context
    
    
class AssignmentActionView(
    LoginRequiredMixin,
    AssignmentAccessMixin,
    AssignmentServiceFormView,
):
    """Handle a form that performs one Assignment lifecycle action."""

    def check_assignment_permission(self):
        if not self.action_policy(self.request.user, self.assignment):
            raise DjangoPermissionDenied(
                "You do not have permission to perform this action."
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = self.assignment
        return context

    def form_valid(self, form):
        """Run the action against the Assignment loaded from the URL."""
        return self.save_assignment(
            self.operation,
            form,
            redirect_assignment_id=self.assignment.pk,
            actor=self.request.user,
            assignment=self.assignment,
            **form.cleaned_data,
        )

class AssignmentCheckInView(AssignmentActionView):
    """Let authorized staff check a student into a reserved bed."""

    form_class = AssignmentCheckInForm
    template_name = "assignments/check_in_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_check_in)
    operation = staticmethod(AssignmentService.check_in)


class ReservationCancellationView(AssignmentActionView):
    """Let an authorized user cancel a reservation and record the reason."""

    form_class = ReservationCancellationForm
    template_name = "assignments/cancel_reservation_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_cancel_reservation)
    operation = staticmethod(AssignmentService.cancel_reservation)
    
    
class AssignmentExtensionRequestView(AssignmentActionView):
    """Let the student request a later deadline for their reservation."""

    form_class = AssignmentExtensionRequestForm
    template_name = "assignments/request_extension_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_request_extension)
    operation = staticmethod(AssignmentService.request_extension)


class CheckoutRequestView(AssignmentActionView):
    """Let the student request checkout from their current stay."""

    form_class = CheckoutRequestForm
    template_name = "assignments/request_checkout_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_request_checkout)
    operation = staticmethod(AssignmentService.request_checkout)


class AssignmentWorkflowDecisionView(AssignmentActionView):
    """Load a workflow request from the Assignment shown in the URL."""

    assignment_lookup = "assignment_id"

    def check_assignment_permission(self):
        try:
            self.workflow_request = get_object_or_404(
                self.request_model,
                pk=self.kwargs["request_id"],
                **{self.assignment_lookup: self.assignment.pk},
            )
        except (DjangoValidationError, ValueError, OverflowError) as exc:
            raise Http404("Assignment request not found.") from exc

        if not self.can_perform_workflow_action():
            raise DjangoPermissionDenied(
                "You do not have permission to perform this action."
            )

    def can_perform_workflow_action(self):
        """Check the policy for this workflow record."""
        return self.action_policy(self.request.user, self.workflow_request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workflow_request"] = self.workflow_request
        return context

    def form_valid(self, form):
        return self.save_assignment(
            self.operation,
            form,
            redirect_assignment_id=self.assignment.pk,
            actor=self.request.user,
            **{self.request_argument: self.workflow_request},
            **form.cleaned_data,
        )


class AssignmentExtensionDecisionView(AssignmentWorkflowDecisionView):
    """Let an authorized reviewer approve or reject a deadline extension."""

    form_class = WorkflowDecisionForm
    template_name = "assignments/decide_extension_form.html"
    request_model = AssignmentExtension
    request_argument = "extension"
    action_policy = staticmethod(AssignmentPolicy.can_decide_extension)
    operation = staticmethod(AssignmentService.decide_extension)


class CheckoutDecisionView(AssignmentWorkflowDecisionView):
    """Let an authorized reviewer decide a checkout request."""

    form_class = CheckoutDecisionForm
    template_name = "assignments/decide_checkout_form.html"
    request_model = CheckoutRequest
    request_argument = "checkout_request"
    action_policy = staticmethod(AssignmentPolicy.can_resolve_checkout_request)
    operation = staticmethod(AssignmentService.resolve_checkout_request)
    
class AssignmentEligibilityDecisionView(AssignmentActionView):
    """Let a scoped Building Manager or Global Admin decide the review."""

    form_class = AssignmentEligibilityDecisionForm
    template_name = "assignments/decide_eligibility_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_review_eligibility)
    operation = staticmethod(AssignmentService.decide_eligibility_review)


class AssignmentTerminationView(AssignmentActionView):
    """End a checked-in stay through the Assignment service."""

    form_class = AssignmentTerminationForm
    template_name = "assignments/terminate_assignment_form.html"
    action_policy = staticmethod(AssignmentPolicy.can_terminate_assignment)
    operation = staticmethod(AssignmentService.terminate_assignment)
    
class AssignmentListView(LoginRequiredMixin, ListView):
    """Show current reservations and stays, with an option to see history."""

    template_name = "assignments/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 25

    @property
    def show_history(self):
        return self.request.GET.get("scope") == "all"

    def get_queryset(self):
        assignments = assignments_visible_to(self.request.user)

        if not self.show_history:
            assignments = assignments.filter(
                status__in=(
                    Assignment.Status.RESERVED,
                    Assignment.Status.CHECKED_IN,
                ),
            )

        return assignments.order_by("-reserved_at", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_history"] = self.show_history
        return context