
from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.campus.campus_model import Campus
from apps.core.policies import AccommodationPolicy

from apps.accommodation.views.base import AccommodationBaseView
from apps.core.exceptions import PermissionDenied


class CampusDetailView(AccommodationBaseView):
    """
    Display one campus and its basic management information.
    """

    template_name = "accommodation/campus/campus_detail.html"

    def get(self, request, pk, *args, **kwargs):
        campus = get_object_or_404(
            Campus.objects.select_related("university"),
            pk=pk,
        )

        if not AccommodationPolicy.can_view_campuses(
            request.user,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view campuses."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "campus": campus,
            },
        )
