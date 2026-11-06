from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accommodation.models.building.building_model import Building
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BuildingListView(BuildingBaseView):
    template_name = "accommodation/building/building_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_building(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view buildings."
                )
            )

        buildings = (
            Building.objects
            .select_related(
                "campus",
                "campus__university",
                "default_bed_configuration",
            )
            .order_by("campus__name", "building_number")
        )

        paginator = Paginator(buildings, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "buildings": page_obj.object_list,
                "page_obj": page_obj,
            },
        )