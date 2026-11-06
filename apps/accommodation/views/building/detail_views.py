from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.building.building_model import Building
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BuildingDetailView(BuildingBaseView):
    template_name = "accommodation/building/building_detail.html"

    def get(self, request, *args, **kwargs):
        building = get_object_or_404(
            Building.objects.select_related(
                "campus",
                "campus__university",
                "default_bed_configuration",
            ),
            pk=kwargs["pk"],
        )

        if not AccommodationPolicy.can_view_building(
            request.user,
            building,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view this building."
                )
            )

        return render(
            request,
            self.template_name,
            {"building": building},
        )