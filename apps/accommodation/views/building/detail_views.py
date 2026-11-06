from django.db.models import Prefetch

from apps.accommodation.models.building.building_model import Building
from apps.accommodation.views.base import BuildingScopedDetailView


class BuildingDetailView(BuildingScopedDetailView):
    model = Building
    template_name = "accommodation/building/detail.html"
    context_object_name = "building"

    policy_method = "can_view_building"

    # A building is the scope boundary for this resource.
    building_lookup = "pk"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "campus",
                "campus__university",
                "default_bed_configuration",
            )
            .prefetch_related("floors")
        )