from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.forms.room.room_forms import (
    RoomBedConfigurationForm,
)
from apps.accommodation.models.room.room_model import Room
from apps.accommodation.services.room_service import RoomService
from apps.accommodation.views.building.base import BuildingBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class RoomOperationBaseView(BuildingBaseView):
    """
    Shared functionality for room-level operational actions.
    """

    def get_room(self):
        return get_object_or_404(
            Room.objects.select_related(
                "floor",
                "floor__building",
            ),
            pk=self.kwargs["pk"],
        )

    def check_permission(self, request, room):
        if AccommodationPolicy.can_view_room(request.user):
            return True

        self.handle_domain_error(
            PermissionDenied(
                "You are not permitted to manage this room."
            )
        )

        return False


class RoomBedConfigurationView(RoomOperationBaseView):
    """
    Set or remove the Room's bed-configuration override.

    The selected configuration must be valid for the room's
    existing physical bed positions.
    """

    template_name = (
        "accommodation/room/room_bed_configuration_form.html"
    )

    operation_label = None
    success_message = None
    service_method = None

    form_class = RoomBedConfigurationForm

    def get_form(self, room):
        return self.form_class(
            initial={
                "bed_configuration": (
                    room.bed_configuration_override
                ),
            }
        )

    def get(self, request, *args, **kwargs):
        room = self.get_room()

        if not self.check_permission(request, room):
            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        form = self.get_form(room)

        return render(
            request,
            self.template_name,
            {
                "room": room,
                "form": form,
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        room = self.get_room()

        if not self.check_permission(request, room):
            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        form = self.form_class(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "room": room,
                    "form": form,
                    "operation_label": self.operation_label,
                },
            )

        service_method = getattr(
            RoomService,
            self.service_method,
        )

        try:
            updated_room = self.execute_operation(
                service_method=service_method,
                actor=request.user,
                room=room,
                cleaned_data=form.cleaned_data,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        self.add_success_message(self.success_message)

        return redirect(
            "accommodation:room-detail",
            pk=updated_room.pk,
        )

    def execute_operation(
        self,
        service_method,
        actor,
        room,
        cleaned_data,
    ):
        raise NotImplementedError


class RoomSetBedConfigurationView(RoomBedConfigurationView):
    operation_label = "Change Room Bed Configuration"
    success_message = (
        "Room bed configuration updated successfully."
    )

    service_method = "set_bed_configuration_override"

    def execute_operation(
        self,
        service_method,
        actor,
        room,
        cleaned_data,
    ):
        return service_method(
            actor=actor,
            room=room,
            configuration=cleaned_data["bed_configuration"],
        )


class RoomRemoveBedConfigurationView(RoomOperationBaseView):
    """
    Remove the Room override and restore the inherited configuration.
    """

    template_name = (
        "accommodation/room/room_confirm_operation.html"
    )

    def get(self, request, *args, **kwargs):
        room = self.get_room()

        if not self.check_permission(request, room):
            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        return render(
            request,
            self.template_name,
            {
                "room": room,
                "operation_label": (
                    "Remove Room Bed Configuration Override"
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        room = self.get_room()

        if not self.check_permission(request, room):
            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        try:
            updated_room = (
                RoomService.remove_bed_configuration_override(
                    actor=request.user,
                    room=room,
                )
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:room-detail",
                pk=room.pk,
            )

        self.add_success_message(
            "Room bed configuration override removed successfully."
        )

        return redirect(
            "accommodation:room-detail",
            pk=updated_room.pk,
        )