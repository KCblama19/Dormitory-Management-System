
from django.core.paginator import (
    EmptyPage,
    PageNotAnInteger,
    Paginator,
)
from django.shortcuts import render

from apps.accommodation.models.campus.campus_model import Campus
from apps.core.policies import AccommodationPolicy

from apps.accommodation.views.base import AccommodationBaseView


class CampusListView(AccommodationBaseView):
    """
    Display campuses available to authorized accommodation managers.
    """

    template_name = "accommodation/campus/campus_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_campuses(
            request.user,
        ):
            from apps.core.exceptions import PermissionDenied

            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view campuses."
                )
            )

        queryset = Campus.objects.select_related(
            "university",
        ).order_by(
            "name",
        )

        paginator = Paginator(
            queryset,
            self.paginate_by,
        )

        page_number = request.GET.get("page", 1)

        try:
            page_obj = paginator.page(page_number)

        except PageNotAnInteger:
            page_obj = paginator.page(1)

        except EmptyPage:
            page_obj = paginator.page(
                paginator.num_pages,
            )

        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "campuses": page_obj.object_list,
            },
        )
