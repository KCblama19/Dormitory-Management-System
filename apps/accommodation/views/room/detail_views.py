from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.room.room_model import Room
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class RoomDetailView(BuildingBaseView):
    template_name = "accommodation/room/room_detail.html"

    def get(self, request, *args, **kwargs):
        room = get_object_or_404(
            Room.objects.select_related(
                "floor",
                "floor__building",
                "floor__building__campus",
                "floor__bed_configuration_override",
                "floor__building__default_bed_configuration",
                "bed_configuration_override",
            ),
            pk=kwargs["pk"],
        )

        if not AccommodationPolicy.can_view_room(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You are not permitted to view this room."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "room": room,
                "effective_bed_configuration": (
                    room.effective_bed_configuration
                ),
                "beds": room.beds.all().order_by("position"),
            },
        )