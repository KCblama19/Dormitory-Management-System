
from django.urls import path

from apps.accommodation.views.campus.list_views import CampusListView
from apps.accommodation.views.campus.detail_views import CampusDetailView
from apps.accommodation.views.campus.create_views import CampusCreateView
from apps.accommodation.views.campus.update_views import CampusUpdateView
from apps.accommodation.views.campus.operational_views import (
    CampusActivateView,
    CampusDeactivateView,
)


app_name = "accommodation"


urlpatterns = [
    # Campus
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
    
    # Building routes
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
]
