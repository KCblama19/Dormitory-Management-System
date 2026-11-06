from django.shortcuts import redirect, render

from apps.accommodation.forms.building_forms import BuildingForm
from apps.accommodation.services.building_service import BuildingService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BuildingCreateView(BuildingBaseView):
    template_name = "accommodation/building/building_form.html"

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_building(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create buildings."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": BuildingForm(),
                "page_title": "Create Building",
                "submit_label": "Create Building",
            },
        )

    def post(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_building(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create buildings."
                )
            )

        form = BuildingForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Building",
                    "submit_label": "Create Building",
                },
            )

        data = form.cleaned_data

        try:
            building = BuildingService.create_building(
                actor=request.user,
                campus=data["campus"],
                building_number=data["building_number"],
                name=data["name"],
                code=data["code"],
                student_population=data["student_population"],
                gender_policy=data["gender_policy"],
                max_floors=data["max_floors"],
                default_bed_configuration=data[
                    "default_bed_configuration"
                ],
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Building",
                    "submit_label": "Create Building",
                },
            )

        self.add_success_message("Building created successfully.")

        return redirect(
            "accommodation:building-detail",
            pk=building.pk,
        )