from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class FloorListView(BuildingBaseView):
    template_name = "accommodation/floor/floor_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_floor(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view floors."
                )
            )

        floors = (
            Floor.objects
            .select_related(
                "building",
                "building__campus",
                "bed_configuration_override",
            )
            .order_by(
                "building__campus__name",
                "building__building_number",
                "floor_number",
            )
        )

        paginator = Paginator(floors, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "floors": page_obj.object_list,
                "page_obj": page_obj,
            },
        )