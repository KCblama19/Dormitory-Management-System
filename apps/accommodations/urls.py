from django.urls import path

# -----------------------
# CAMPUS IMPORTS
# -----------------------
from apps.accommodations.views.campus.list_views import CampusListView
from apps.accommodations.views.campus.detail_views import CampusDetailView
from apps.accommodations.views.campus.create_views import CampusCreateView
from apps.accommodations.views.campus.update_views import CampusUpdateView
from apps.accommodations.views.campus.operational_views import (
    CampusActivateView,
    CampusDeactivateView,
)

# -----------------------
# BUILDING IMPORTS
# -----------------------
from apps.accommodations.views.building.list_views import BuildingListView
from apps.accommodations.views.building.detail_views import BuildingDetailView
from apps.accommodations.views.building.create_views import BuildingCreateView
from apps.accommodations.views.building.update_views import BuildingUpdateView
from apps.accommodations.views.building.operational_views import (
    BuildingActivateView,
    BuildingDeactivateView,
)
from apps.accommodations.views.building.configuration_views import (
    BuildingGenderPolicyChangeView,
    BuildingPopulationChangeView,
    BuildingDefaultBedConfigurationChangeView,
)

# -----------------------
# FLOOR IMPORTS
# -----------------------
from apps.accommodations.views.floor.list_views import FloorListView
from apps.accommodations.views.floor.detail_views import FloorDetailView
from apps.accommodations.views.floor.create_views import FloorCreateView
from apps.accommodations.views.floor.update_views import FloorUpdateView
from apps.accommodations.views.floor.operational_views import (
    FloorActivateView,
    FloorDeactivateView,
    FloorMaintenanceView,
    FloorRemoveRestrictionView,
    FloorSetRestrictionView,
    FloorSetBedConfigurationView,
    FloorRemoveBedConfigurationView,
)

# -----------------------
# ROOM IMPORTS
# -----------------------
from apps.accommodations.views.room.list_views import RoomListView
from apps.accommodations.views.room.detail_views import RoomDetailView
from apps.accommodations.views.room.create_views import RoomCreateView
from apps.accommodations.views.room.operational_views import (
    RoomSetBedConfigurationView,
    RoomRemoveBedConfigurationView,
)

# -----------------------
# BED IMPORTS
# -----------------------
from apps.accommodations.views.bed.list_views import BedListView
from apps.accommodations.views.bed.detail_views import BedDetailView
from apps.accommodations.views.bed.create_views import BedCreateView
from apps.accommodations.views.bed.update_views import BedPositionUpdateView
from apps.accommodations.views.bed.operational_views import (
    BedSetAvailableView,
    BedSetMaintenanceView,
    BedSetOutOfServiceView,
    BedRestoreView,
)

# -----------------------
# BED CONFIGURATION IMPORTS
# -----------------------
from apps.accommodations.views.bed_configuration.list_views import (
    BedConfigurationListView,
)
from apps.accommodations.views.bed_configuration.detail_views import (
    BedConfigurationDetailView,
)
from apps.accommodations.views.bed_configuration.create_views import (
    BedConfigurationCreateView,
)
from apps.accommodations.views.bed_configuration.update_views import (
    BedConfigurationUpdateView,
    BedConfigurationActivateView,
    BedConfigurationDeactivateView,
)


app_name = "accommodation"


urlpatterns = [
    # -----------------------
    # CAMPUS ROUTES
    # -----------------------
    path(
        "campuses/",
        CampusListView.as_view(),
        name="campus-list",
    ),
    path(
        "campuses/create/",
        CampusCreateView.as_view(),
        name="campus-create",
    ),
    path(
        "campuses/<int:pk>/",
        CampusDetailView.as_view(),
        name="campus-detail",
    ),
    path(
        "campuses/<int:pk>/update/",
        CampusUpdateView.as_view(),
        name="campus-update",
    ),
    path(
        "campuses/<int:pk>/activate/",
        CampusActivateView.as_view(),
        name="campus-activate",
    ),
    path(
        "campuses/<int:pk>/deactivate/",
        CampusDeactivateView.as_view(),
        name="campus-deactivate",
    ),

    # -----------------------
    # BUILDING ROUTES
    # -----------------------
    path(
        "buildings/",
        BuildingListView.as_view(),
        name="building-list",
    ),
    path(
        "buildings/create/",
        BuildingCreateView.as_view(),
        name="building-create",
    ),
    path(
        "buildings/<int:pk>/",
        BuildingDetailView.as_view(),
        name="building-detail",
    ),
    path(
        "buildings/<int:pk>/update/",
        BuildingUpdateView.as_view(),
        name="building-update",
    ),
    path(
        "buildings/<int:pk>/activate/",
        BuildingActivateView.as_view(),
        name="building-activate",
    ),
    path(
        "buildings/<int:pk>/deactivate/",
        BuildingDeactivateView.as_view(),
        name="building-deactivate",
    ),
    path(
        "buildings/<int:pk>/change-gender-policy/",
        BuildingGenderPolicyChangeView.as_view(),
        name="building-change-gender-policy",
    ),
    path(
        "buildings/<int:pk>/change-population/",
        BuildingPopulationChangeView.as_view(),
        name="building-change-population",
    ),
    path(
        "buildings/<int:pk>/change-default-bed-configuration/",
        BuildingDefaultBedConfigurationChangeView.as_view(),
        name="building-change-default-bed-configuration",
    ),

    # -----------------------
    # FLOOR ROUTES
    # -----------------------
    path(
        "floors/",
        FloorListView.as_view(),
        name="floor-list",
    ),
    path(
        "floors/create/",
        FloorCreateView.as_view(),
        name="floor-create",
    ),
    path(
        "floors/<int:pk>/",
        FloorDetailView.as_view(),
        name="floor-detail",
    ),
    path(
        "floors/<int:pk>/update/",
        FloorUpdateView.as_view(),
        name="floor-update",
    ),

    # Floor status operations
    path(
        "floors/<int:pk>/activate/",
        FloorActivateView.as_view(),
        name="floor-activate",
    ),
    path(
        "floors/<int:pk>/deactivate/",
        FloorDeactivateView.as_view(),
        name="floor-deactivate",
    ),
    path(
        "floors/<int:pk>/maintenance/",
        FloorMaintenanceView.as_view(),
        name="floor-maintenance",
    ),

    # Floor restriction operations
    path(
        "floors/<int:pk>/restrict/",
        FloorSetRestrictionView.as_view(),
        name="floor-set-restriction",
    ),
    path(
        "floors/<int:pk>/remove-restriction/",
        FloorRemoveRestrictionView.as_view(),
        name="floor-remove-restriction",
    ),

    # Floor bed-configuration operations
    path(
        "floors/<int:pk>/bed-configuration/",
        FloorSetBedConfigurationView.as_view(),
        name="floor-set-bed-configuration",
    ),
    path(
        "floors/<int:pk>/remove-bed-configuration/",
        FloorRemoveBedConfigurationView.as_view(),
        name="floor-remove-bed-configuration",
    ),

    # -----------------------
    # ROOM ROUTES
    # -----------------------
    path(
        "rooms/",
        RoomListView.as_view(),
        name="room-list",
    ),
    path(
        "rooms/create/",
        RoomCreateView.as_view(),
        name="room-create",
    ),
    path(
        "rooms/<int:pk>/",
        RoomDetailView.as_view(),
        name="room-detail",
    ),

    # Room bed-configuration operations
    path(
        "rooms/<int:pk>/bed-configuration/",
        RoomSetBedConfigurationView.as_view(),
        name="room-set-bed-configuration",
    ),
    path(
        "rooms/<int:pk>/remove-bed-configuration/",
        RoomRemoveBedConfigurationView.as_view(),
        name="room-remove-bed-configuration",
    ),

    # -----------------------
    # BED ROUTES
    # -----------------------
    path(
        "beds/",
        BedListView.as_view(),
        name="bed-list",
    ),
    path(
        "beds/create/",
        BedCreateView.as_view(),
        name="bed-create",
    ),
    path(
        "beds/<int:pk>/",
        BedDetailView.as_view(),
        name="bed-detail",
    ),
    path(
        "beds/<int:pk>/update-position/",
        BedPositionUpdateView.as_view(),
        name="bed-update-position",
    ),

    # Bed status operations
    path(
        "beds/<int:pk>/available/",
        BedSetAvailableView.as_view(),
        name="bed-set-available",
    ),
    path(
        "beds/<int:pk>/maintenance/",
        BedSetMaintenanceView.as_view(),
        name="bed-set-maintenance",
    ),
    path(
        "beds/<int:pk>/out-of-service/",
        BedSetOutOfServiceView.as_view(),
        name="bed-set-out-of-service",
    ),
    path(
        "beds/<int:pk>/restore/",
        BedRestoreView.as_view(),
        name="bed-restore",
    ),

    # -----------------------
    # BED CONFIGURATION ROUTES
    # -----------------------
    path(
        "bed-configurations/",
        BedConfigurationListView.as_view(),
        name="bed-configuration-list",
    ),
    path(
        "bed-configurations/create/",
        BedConfigurationCreateView.as_view(),
        name="bed-configuration-create",
    ),
    path(
        "bed-configurations/<int:pk>/",
        BedConfigurationDetailView.as_view(),
        name="bed-configuration-detail",
    ),
    path(
        "bed-configurations/<int:pk>/update/",
        BedConfigurationUpdateView.as_view(),
        name="bed-configuration-update",
    ),
    path(
        "bed-configurations/<int:pk>/activate/",
        BedConfigurationActivateView.as_view(),
        name="bed-configuration-activate",
    ),
    path(
        "bed-configurations/<int:pk>/deactivate/",
        BedConfigurationDeactivateView.as_view(),
        name="bed-configuration-deactivate",
    ),
]