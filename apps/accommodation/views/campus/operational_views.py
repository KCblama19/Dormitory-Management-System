
from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.models.campus.campus_model import Campus
from apps.accommodation.services.campus_service import CampusService
from apps.accommodation.views.base import AccommodationBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class CampusStateChangeView(AccommodationBaseView):
    """
    Shared HTTP workflow for campus activation and deactivation.

    GET displays a confirmation page.
    POST delegates the state change to CampusService.
    """

    template_name = "accommodation/campus/campus_confirm_operation.html"

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    def get_campus(self):
        return get_object_or_404(
            Campus.objects.select_related("university"),
            pk=self.kwargs["pk"],
        )

    def is_authorized(self, actor, campus):
        policy = getattr(
            AccommodationPolicy,
            self.policy_method,
        )

        return policy(actor, campus)

    def get(self, request, *args, **kwargs):
        campus = self.get_campus()

        if not self.is_authorized(request.user, campus):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to perform "
                    "this operation."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "campus": campus,
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        campus = self.get_campus()

        service = getattr(
            CampusService,
            self.service_method,
        )

        try:
            updated_campus = service(
                actor=request.user,
                campus=campus,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:campus-detail",
                pk=campus.pk,
            )

        self.add_success_message(self.success_message)

        return redirect(
            "accommodation:campus-detail",
            pk=updated_campus.pk,
        )


class CampusActivateView(CampusStateChangeView):
    """
    Confirm and activate an inactive campus.
    """

    operation_label = "Activate Campus"

    success_message = "Campus activated successfully."

    policy_method = "can_activate_campus"

    service_method = "activate_campus"


class CampusDeactivateView(CampusStateChangeView):
    """
    Confirm and deactivate an active campus.
    """

    operation_label = "Deactivate Campus"

    success_message = "Campus deactivated successfully."

    policy_method = "can_deactivate_campus"

    service_method = "deactivate_campus"
