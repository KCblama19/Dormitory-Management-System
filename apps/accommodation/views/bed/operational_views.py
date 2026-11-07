
from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.forms.bed_forms import (
    BedStatusOperationForm,
)
from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.services.bed_service import BedService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedOperationBaseView(BuildingBaseView):
    """
    Shared HTTP handling for bed operational operations.

    Each concrete view defines the service method and operation label.
    Service-level authorization remains authoritative.
    """

    template_name = "accommodation/bed/bed_confirm_operation.html"
    form_class = BedStatusOperationForm

    operation_label = None
    success_message = None
    service_method = None

    def get_bed(self):
        return get_object_or_404(
            Bed.objects.select_related(
                "room",
                "room__floor",
                "room__floor__building",
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        bed = self.get_bed()

        if not AccommodationPolicy.can_view_bed(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You are not permitted to view this bed."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "bed": bed,
                "form": self.form_class(),
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        bed = self.get_bed()
        form = self.form_class(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "bed": bed,
                    "form": form,
                    "operation_label": self.operation_label,
                },
            )

        service_method = getattr(
            BedService,
            self.service_method,
        )

        try:
            updated_bed = service_method(
                actor=request.user,
                bed=bed,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:bed-detail",
                pk=bed.pk,
            )

        self.add_success_message(self.success_message)

        return redirect(
            "accommodation:bed-detail",
            pk=updated_bed.pk,
        )


class BedSetAvailableView(BedOperationBaseView):
    operation_label = "Set Bed as Available"
    success_message = "Bed is now available."

    service_method = "set_available"


class BedSetMaintenanceView(BedOperationBaseView):
    operation_label = "Set Bed for Maintenance"
    success_message = "Bed set for maintenance."

    service_method = "set_maintenance"


class BedSetOutOfServiceView(BedOperationBaseView):
    operation_label = "Set Bed Out of Service"
    success_message = "Bed marked as out of service."

    service_method = "set_out_of_service"


class BedRestoreView(BedOperationBaseView):
    operation_label = "Restore Bed"
    success_message = "Bed restored successfully."

    service_method = "restore_bed"
