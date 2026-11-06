from django.shortcuts import redirect, render

from apps.accommodation.forms.room.room_forms import CreateRoomForm
from apps.accommodation.services.room_service import RoomService
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import DomainError


class RoomCreateView(BuildingBaseView):
    template_name = "accommodation/room/room_form.html"
    form_class = CreateRoomForm

    def get_form(self, data=None):
        form = self.form_class(data)

        # Only operational floors should be selectable.
        form.fields["floor"].queryset = (
            form.fields["floor"].queryset
            .filter(
                is_active=True,
                status="ACTIVE",
                building__is_active=True,
            )
            .select_related("building")
            .order_by(
                "building__building_number",
                "floor_number",
            )
        )

        return form

    def get(self, request, *args, **kwargs):
        form = self.get_form()

        return render(
            request,
            self.template_name,
            {"form": form},
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form},
            )

        try:
            room = RoomService.create_room(
                actor=request.user,
                floor=form.cleaned_data["floor"],
                bed_configuration_override=(
                    form.cleaned_data["bed_configuration_override"]
                ),
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return render(
                request,
                self.template_name,
                {"form": form},
            )

        self.add_success_message(
            f"Room {room.full_code} created successfully."
        )

        return redirect(
            "accommodation:room-detail",
            pk=room.pk,
        )