from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accommodation.models.room.room_model import Room
from apps.accommodation.views.base import BuildingBaseView
from apps.core.policies import AccommodationPolicy

from apps.core.exceptions import PermissionDenied


class RoomListView(BuildingBaseView):
    template_name = "accommodation/room/room_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_room(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You are not permitted to view rooms."
                )
            )

        rooms = (
            Room.objects
            .select_related(
                "floor",
                "floor__building",
                "floor__building__campus",
                "bed_configuration_override",
            )
            .order_by(
                "floor__building__campus__name",
                "floor__building__building_number",
                "floor__floor_number",
                "position",
            )
        )

        paginator = Paginator(rooms, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "rooms": page_obj.object_list,
            },
        )