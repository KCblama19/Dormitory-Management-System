from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class FloorDetailView(BuildingBaseView):
    template_name = "accommodation/floor/floor_detail.html"

    def get(self, request, *args, **kwargs):
        floor = get_object_or_404(
            Floor.objects.select_related(
                "building",
                "building__campus",
                "building__default_bed_configuration",
                "bed_configuration_override",
            ),
            pk=kwargs["pk"],
        )

        if not AccommodationPolicy.can_view_floor(
            request.user,
            floor,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view this floor."
                )
            )

        return render(
            request,
            self.template_name,
            {"floor": floor},
        )