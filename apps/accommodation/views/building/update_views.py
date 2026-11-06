from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.forms.building_forms import BuildingForm
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.services.building_service import BuildingService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BuildingUpdateView(BuildingBaseView):
    template_name = "accommodation/building/building_form.html"

    def get_building(self):
        return get_object_or_404(
            Building.objects.select_related(
                "campus",
                "default_bed_configuration",
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        building = self.get_building()

        if not AccommodationPolicy.can_update_building(
            request.user,
            building,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this building."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": BuildingForm(instance=building),
                "building": building,
                "page_title": "Update Building",
                "submit_label": "Save Changes",
            },
        )

    def post(self, request, *args, **kwargs):
        building = self.get_building()

        if not AccommodationPolicy.can_update_building(
            request.user,
            building,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this building."
                )
            )

        form = BuildingForm(request.POST, instance=building)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "building": building,
                    "page_title": "Update Building",
                    "submit_label": "Save Changes",
                },
            )

        # The service accepts only editable fields. The campus is
        # intentionally excluded from the update operation.
        editable_fields = {
            "building_number",
            "name",
            "code",
            "student_population",
            "gender_policy",
            "max_floors",
            "default_bed_configuration",
        }

        changes = {
            field: form.cleaned_data[field]
            for field in form.changed_data
            if field in editable_fields
        }

        try:
            updated_building = BuildingService.update_building(
                actor=request.user,
                building=building,
                **changes,
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "building": building,
                    "page_title": "Update Building",
                    "submit_label": "Save Changes",
                },
            )

        self.add_success_message("Building updated successfully.")

        return redirect(
            "accommodation:building-detail",
            pk=updated_building.pk,
        )