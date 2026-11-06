from django.urls import path

from apps.profiles.views.student.academic_year_views import (
    AcademicYearListView,
    AcademicYearCreateView,
)

app_name = "profiles"

urlpatterns = [
    path(
        "academic-years/", 
        AcademicYearListView.as_view(),
        name="academic_year_list",
    ),
    path(
        "academic-years/create",
        AcademicYearCreateView.as_view(),
        name="academic_year_create",
    )
]
