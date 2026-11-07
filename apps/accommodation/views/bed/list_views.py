
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedListView(BuildingBaseView):
    template_name = "accommodation/bed/bed_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_bed(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You are not permitted to view beds."
                )
            )

        beds = (
            Bed.objects
            .select_related(
                "room",
                "room__floor",
                "room__floor__building",
                "room__floor__building__campus",
            )
            .order_by(
                "room__floor__building__campus__name",
                "room__floor__building__building_number",
                "room__floor__floor_number",
                "room__position",
                "position",
            )
        )

        paginator = Paginator(beds, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "beds": page_obj.object_list,
            },
        )
