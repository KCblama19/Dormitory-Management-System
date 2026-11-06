from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.views.base import BuildingScopedDetailView


class BedDetailView(BuildingScopedDetailView):
    model = Bed
    template_name = "accommodation/bed/detail.html"
    context_object_name = "bed"

    policy_method = "can_view_bed"

    # Bed -> Room -> Floor -> Building
    building_lookup = "room__floor__building_id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "room",
                "room__floor",
                "room__floor__building",
                "room__floor__building__campus",
            )
        )