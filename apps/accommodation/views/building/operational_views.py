from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.models.building.building_model import Building
from apps.accommodation.services.building_service import BuildingService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BuildingStateChangeView(BuildingBaseView):
    template_name = "accommodation/building/building_confirm_operation.html"

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    def get_building(self):
        return get_object_or_404(
            Building.objects.select_related("campus"),
            pk=self.kwargs["pk"],
        )

    def is_authorized(self, actor, building):
        policy = getattr(AccommodationPolicy, self.policy_method)
        return policy(actor, building)

    def get(self, request, *args, **kwargs):
        building = self.get_building()

        if not self.is_authorized(request.user, building):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to perform this operation."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "building": building,
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        building = self.get_building()
        service = getattr(BuildingService, self.service_method)

        try:
            service(
                actor=request.user,
                building=building,
            )

        except DomainError as error:
            self.add_error_message(error.message)
            return redirect(
                "accommodation:building-detail",
                pk=building.pk,
            )

        self.add_success_message(self.success_message)

        return redirect(
            "accommodation:building-detail",
            pk=building.pk,
        )


class BuildingActivateView(BuildingStateChangeView):
    operation_label = "Activate Building"
    success_message = "Building activated successfully."
    policy_method = "can_activate_building"
    service_method = "activate_building"


class BuildingDeactivateView(BuildingStateChangeView):
    operation_label = "Deactivate Building"
    success_message = "Building deactivated successfully."
    policy_method = "can_deactivate_building"
    service_method = "deactivate_building"