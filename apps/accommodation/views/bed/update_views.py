
from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.forms.bed_forms import (
    UpdateBedPositionForm,
)
from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.services.bed_service import BedService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError
from apps.core.policies import AccommodationPolicy

from apps.core.exceptions import DomainError, PermissionDenied

class BedPositionUpdateView(BuildingBaseView):
    template_name = "accommodation/bed/bed_position_form.html"
    form_class = UpdateBedPositionForm

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

        form = self.form_class(
            initial={"position": bed.position}
        )

        return render(
            request,
            self.template_name,
            {
                "bed": bed,
                "form": form,
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
                },
            )

        try:
            updated_bed = BedService.update_bed_position(
                actor=request.user,
                bed=bed,
                position=form.cleaned_data["position"],
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return render(
                request,
                self.template_name,
                {
                    "bed": bed,
                    "form": form,
                },
            )

        self.add_success_message(
            f"Bed position updated successfully. New code: {updated_bed.code}"
        )

        return redirect(
            "accommodation:bed-detail",
            pk=updated_bed.pk,
        )
