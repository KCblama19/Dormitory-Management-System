from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.views.base import BuildingScopedDetailView


class FloorDetailView(BuildingScopedDetailView):
    model = Floor
    template_name = "accommodation/floor/detail.html"
    context_object_name = "floor"

    policy_method = "can_view_floor"

    # Floor -> Building
    building_lookup = "building_id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "building",
                "building__campus",
                "building__campus__university",
                "bed_configuration_override",
            )
            .prefetch_related("rooms")
        )