from django.core.exceptions import PermissionDenied as DjangoPermissionDenied

from apps.accommodations.models import Bed, Floor
from apps.assignments.forms import (
    TransferCancellationForm,
    TransferCancellationRequestForm,
    TransferCompletionForm,
    TransferDecisionForm,
    TransferRequestForm,
)
from apps.assignments.models import Assignment, TransferRequest
from apps.assignments.services.transfer_service import TransferService
from dorm_system.apps.assignments.views.views import (
    AssignmentActionView,
    AssignmentWorkflowDecisionView,
)
from apps.core.policies.transfer_policy import TransferPolicy


class TransferRequestView(AssignmentActionView):
    """Let an authorized user request a move from the current Assignment."""

    form_class = TransferRequestForm
    template_name = "assignments/request_transfer_form.html"

    def check_assignment_permission(self):
        source_building = self.assignment.bed.room.floor.building

        if not TransferPolicy.can_request_transfer(
            self.request.user,
            source=self.assignment,
            destination_building=source_building,
        ):
            raise DjangoPermissionDenied(
                "You do not have permission to request a transfer for this assignment."
            )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        beds = (
            Bed.objects.select_related("room__floor__building")
            .filter(
                status=Bed.Status.AVAILABLE,
                room__floor__status=Floor.FloorStatus.ACTIVE,
                room__floor__is_restricted=False,
                room__floor__building__is_active=True,
            )
            .exclude(pk=self.assignment.bed_id)
            .exclude(
                assignments__status__in=(
                    Assignment.Status.RESERVED,
                    Assignment.Status.CHECKED_IN,
                )
            )
        )

        if not TransferPolicy.is_global_admin(self.request.user):
            beds = beds.filter(
                room__floor__building_id=self.assignment.bed.room.floor.building_id,
            )

        kwargs["destination_beds"] = beds
        return kwargs

    def form_valid(self, form):
        # The service checks the selected destination and current bed
        # availability again before accepting the request.
        return self.save_assignment(
            TransferService.request_transfer,
            form,
            redirect_assignment_id=self.assignment.pk,
            actor=self.request.user,
            source_assignment=self.assignment,
            **form.cleaned_data,
        )


class TransferWorkflowView(AssignmentWorkflowDecisionView):
    """Resolve the transfer through its source Assignment."""

    request_model = TransferRequest
    request_argument = "transfer_request"
    assignment_lookup = "source_assignment_id"


class TransferDecisionView(TransferWorkflowView):
    """Let the authorized reviewer approve or reject a transfer."""

    form_class = TransferDecisionForm
    template_name = "assignments/decide_transfer_form.html"

    def can_perform_workflow_action(self):
        return TransferPolicy.can_approve_transfer(
            self.request.user,
            source=self.assignment,
            destination_building=self.workflow_request.destination_bed.room.floor.building,
        )

    def form_valid(self, form):
        if form.cleaned_data["approve"]:
            return self.save_assignment(
                TransferService.approve_transfer,
                form,
                redirect_assignment_id=self.assignment.pk,
                actor=self.request.user,
                transfer_request=self.workflow_request,
                approved_move_date=form.cleaned_data["approved_move_date"],
            )

        return self.save_assignment(
            TransferService.reject_transfer,
            form,
            redirect_assignment_id=self.assignment.pk,
            actor=self.request.user,
            transfer_request=self.workflow_request,
        )


class TransferCompletionView(TransferWorkflowView):
    """Complete a transfer after the student physically moves."""

    form_class = TransferCompletionForm
    template_name = "assignments/complete_transfer_form.html"
    operation = staticmethod(TransferService.complete_transfer)

    def can_perform_workflow_action(self):
        return TransferPolicy.can_complete_transfer(
            self.request.user,
            source=self.assignment,
            destination_building=self.workflow_request.destination_bed.room.floor.building,
        )


class TransferCancellationRequestView(TransferWorkflowView):
    """Let the student ask to cancel a permitted same-building transfer."""

    form_class = TransferCancellationRequestForm
    template_name = "assignments/request_transfer_cancellation_form.html"
    action_policy = staticmethod(TransferPolicy.can_request_transfer_cancellation)
    operation = staticmethod(TransferService.request_transfer_cancellation)


class TransferCancellationView(TransferWorkflowView):
    """Let authorized staff carry out a transfer cancellation."""

    form_class = TransferCancellationForm
    template_name = "assignments/cancel_transfer_form.html"
    action_policy = staticmethod(TransferPolicy.can_cancel_transfer)
    operation = staticmethod(TransferService.cancel_transfer)