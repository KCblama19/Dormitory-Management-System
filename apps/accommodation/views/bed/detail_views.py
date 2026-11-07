from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedDetailView(BuildingBaseView):
    template_name = "accommodation/bed/bed_detail.html"

    def get(self, request, *args, **kwargs):
        bed = get_object_or_404(
            Bed.objects.select_related(
                "room",
                "room__floor",
                "room__floor__building",
                "room__floor__building__campus",
            ),
            pk=kwargs["pk"],
        )

        if not AccommodationPolicy.can_view_bed(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You are not permitted to view this bed."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "bed": bed,
                "is_occupied": bed.is_occupied,
                "is_available": bed.is_available,
            },
        )
