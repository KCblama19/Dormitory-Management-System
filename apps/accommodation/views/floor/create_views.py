from django.shortcuts import redirect, render

from apps.accommodation.forms.floor_forms import CreateFloorForm
from apps.accommodation.services.floor_service import FloorService
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class FloorCreateView(BuildingBaseView):
    template_name = "accommodation/floor/floor_form.html"

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_floor(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create floors."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": CreateFloorForm(),
                "page_title": "Create Floor",
                "submit_label": "Create Floor",
            },
        )

    def post(self, request, *args, **kwargs):
        form = CreateFloorForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Floor",
                    "submit_label": "Create Floor",
                },
            )

        data = form.cleaned_data

        # The service performs the authoritative authorization check.
        # Its policy requires the actor to be allowed to create floors
        # in the selected Building.
        try:
            floor = FloorService.create_floor(
                actor=request.user,
                building=data["building"],
                max_rooms_per_floor=data["max_rooms_per_floor"],
                gender_configuration=data["gender_configuration"] or None,
                bed_configuration_override=(
                    data["bed_configuration_override"]
                ),
                restriction_note=data["restriction_note"].strip() or None,
                is_restricted=data["is_restricted"],
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Floor",
                    "submit_label": "Create Floor",
                },
            )

        self.add_success_message("Floor created successfully.")

        return redirect(
            "accommodation:floor-detail",
            pk=floor.pk,
        )