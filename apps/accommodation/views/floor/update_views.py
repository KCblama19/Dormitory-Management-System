from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.forms.floor_forms import FloorForm
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.services.floor_service import FloorService
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class FloorUpdateView(BuildingBaseView):
    template_name = "accommodation/floor/floor_form.html"

    def get_floor(self):
        return get_object_or_404(
            Floor.objects.select_related("building"),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not AccommodationPolicy.can_update_floor(
            request.user,
            floor,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this floor."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": FloorForm(instance=floor),
                "floor": floor,
                "page_title": "Update Floor",
                "submit_label": "Save Changes",
            },
        )

    def post(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not AccommodationPolicy.can_update_floor(
            request.user,
            floor,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this floor."
                )
            )

        form = FloorForm(request.POST, instance=floor)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "floor": floor,
                    "page_title": "Update Floor",
                    "submit_label": "Save Changes",
                },
            )

        changes = {
            field: form.cleaned_data[field]
            for field in form.changed_data
        }

        try:
            updated_floor = FloorService.update_floor(
                actor=request.user,
                floor=floor,
                **changes,
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "floor": floor,
                    "page_title": "Update Floor",
                    "submit_label": "Save Changes",
                },
            )

        self.add_success_message("Floor updated successfully.")

        return redirect(
            "accommodation:floor-detail",
            pk=updated_floor.pk,
        )