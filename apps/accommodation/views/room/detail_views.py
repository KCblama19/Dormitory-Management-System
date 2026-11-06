from apps.accommodation.models.room.room_model import Room
from apps.accommodation.views.base import BuildingScopedDetailView


class RoomDetailView(BuildingScopedDetailView):
    model = Room
    template_name = "accommodation/room/detail.html"
    context_object_name = "room"

    policy_method = "can_view_room"

    # Room -> Floor -> Building
    building_lookup = "floor__building_id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "floor",
                "floor__building",
                "floor__building__campus",
                "bed_configuration_override",
            )
            .prefetch_related("beds")
        )