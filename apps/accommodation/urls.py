
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
]
