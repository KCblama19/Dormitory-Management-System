from django.urls import path

from apps.accommodation import views

app_name = "accommodation"

urlpatterns = [
    path("", views.AccommodationDashboardView.as_view(), name="dashboard"),
    path("buildings/", views.BuildingListView.as_view(), name="buildings"),
    path("floors/", views.FloorListView.as_view(), name="floors"),
    path("rooms/", views.RoomListView.as_view(), name="rooms"),
    path("beds/", views.BedListView.as_view(), name="beds"),
    path(
        "bed-configurations/",
        views.BedConfigurationListView.as_view(),
        name="bed-configurations",
    ),
]