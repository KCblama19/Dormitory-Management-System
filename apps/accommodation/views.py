
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView, ListView

from apps.accommodation.models.campus.campus_model import Campus
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.models.room.room_model import Room
from apps.accommodation.models.bed.bed_model import Bed
from apps.accommodation.models.bed.bed_configuration import BedConfiguration

from apps.core.policies import AccommodationPolicy


class AccommodationAccessMixin(LoginRequiredMixin):
    """
    Provides role-level authorization for accommodation views.

    Object-level authorization must still be checked separately
    when a view operates on a specific accommodation object.
    """

    policy_method = None

    def dispatch(self, request, *args, **kwargs):
        if self.policy_method:
            policy = getattr(
                AccommodationPolicy,
                self.policy_method,
            )

            if not policy(request.user):
                raise PermissionDenied(
                    "You do not have permission to access this page."
                )

        return super().dispatch(request, *args, **kwargs)


class BuildingScopedListView(LoginRequiredMixin, ListView):
    """
    Base class for accommodation lists that are restricted
    to the authenticated staff member's assigned building.

    Administrators can access all records.
    Building Managers and Building Staff can access only
    records belonging to their assigned building.
    """

    def get_actor_building(self):
        actor = self.request.user

        if AccommodationPolicy.is_global_admin(actor):
            return None

        staff = AccommodationPolicy.active_staff_profile(actor)

        if staff is None:
            raise PermissionDenied(
                "You do not have an active staff profile."
            )

        building = getattr(staff, "building", None)

        if building is None:
            raise PermissionDenied(
                "No building is assigned to this account."
            )

        return building


class AccommodationDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accommodation/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not (
            AccommodationPolicy.can_view_universities(request.user)
            or AccommodationPolicy.can_view_building(request.user)
        ):
            raise PermissionDenied(
                "You do not have permission to access accommodation management."
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor = self.request.user

        if AccommodationPolicy.is_global_admin(actor):
            buildings = Building.objects.select_related(
                "campus",
                "campus__university",
                "default_bed_configuration",
            )

            floors = Floor.objects.select_related(
                "building",
                "building__campus",
            )

            rooms = Room.objects.select_related(
                "floor",
                "floor__building",
            )

            beds = Bed.objects.select_related(
                "room",
                "room__floor",
                "room__floor__building",
            )

        else:
            staff = AccommodationPolicy.active_staff_profile(actor)
            building = getattr(staff, "building", None)

            if building is None:
                raise PermissionDenied(
                    "No building is assigned to this account."
                )

            buildings = Building.objects.filter(
                pk=building.pk,
            ).select_related(
                "campus",
                "campus__university",
                "default_bed_configuration",
            )

            floors = Floor.objects.filter(
                building=building,
            ).select_related(
                "building",
            )

            rooms = Room.objects.filter(
                floor__building=building,
            ).select_related(
                "floor",
                "floor__building",
            )

            beds = Bed.objects.filter(
                room__floor__building=building,
            ).select_related(
                "room",
                "room__floor",
                "room__floor__building",
            )

        context.update({
            "buildings": buildings,
            "floors": floors,
            "rooms": rooms,
            "beds": beds,
            "building_count": buildings.count(),
            "floor_count": floors.count(),
            "room_count": rooms.count(),
            "bed_count": beds.count(),
        })

        return context


class BuildingListView(BuildingScopedListView):
    model = Building
    template_name = "accommodation/building_list.html"
    context_object_name = "buildings"
    paginate_by = 25

    def get_queryset(self):
        actor = self.request.user

        if not AccommodationPolicy.can_view_building(actor):
            raise PermissionDenied(
                "You do not have permission to view buildings."
            )

        queryset = Building.objects.select_related(
            "campus",
            "campus__university",
            "default_bed_configuration",
        )

        building = self.get_actor_building()

        if building is not None:
            queryset = queryset.filter(pk=building.pk)

        return queryset.order_by("campus_id", "building_number")


class FloorListView(BuildingScopedListView):
    model = Floor
    template_name = "accommodation/floor_list.html"
    context_object_name = "floors"
    paginate_by = 25

    def get_queryset(self):
        actor = self.request.user

        if not AccommodationPolicy.can_view_floor(actor):
            raise PermissionDenied(
                "You do not have permission to view floors."
            )

        queryset = Floor.objects.select_related(
            "building",
            "building__campus",
            "bed_configuration_override",
        )

        building = self.get_actor_building()

        if building is not None:
            queryset = queryset.filter(building=building)

        return queryset.order_by(
            "building_id",
            "floor_number",
        )


class RoomListView(BuildingScopedListView):
    model = Room
    template_name = "accommodation/room_list.html"
    context_object_name = "rooms"
    paginate_by = 25

    def get_queryset(self):
        actor = self.request.user

        if not AccommodationPolicy.can_view_room(actor):
            raise PermissionDenied(
                "You do not have permission to view rooms."
            )

        queryset = Room.objects.select_related(
            "floor",
            "floor__building",
            "floor__building__campus",
            "bed_configuration_override",
        )

        building = self.get_actor_building()

        if building is not None:
            queryset = queryset.filter(
                floor__building=building,
            )

        return queryset.order_by(
            "floor__building_id",
            "floor__floor_number",
            "position",
        )


class BedListView(BuildingScopedListView):
    model = Bed
    template_name = "accommodation/bed_list.html"
    context_object_name = "beds"
    paginate_by = 50

    def get_queryset(self):
        actor = self.request.user

        if not AccommodationPolicy.can_view_bed(actor):
            raise PermissionDenied(
                "You do not have permission to view beds."
            )

        queryset = Bed.objects.select_related(
            "room",
            "room__floor",
            "room__floor__building",
        )

        building = self.get_actor_building()

        if building is not None:
            queryset = queryset.filter(
                room__floor__building=building,
            )

        return queryset.order_by(
            "room__floor__building_id",
            "room__floor__floor_number",
            "room__position",
            "position",
        )


class BedConfigurationListView(LoginRequiredMixin, ListView):
    model = BedConfiguration
    template_name = "accommodation/bed_configuration_list.html"
    context_object_name = "bed_configurations"
    paginate_by = 25

    def get_queryset(self):
        actor = self.request.user

        if not AccommodationPolicy.can_view_bed_configurations(actor):
            raise PermissionDenied(
                "You do not have permission to view bed configurations."
            )

        return BedConfiguration.objects.all().order_by(
            "bed_count",
            "name",
        )
