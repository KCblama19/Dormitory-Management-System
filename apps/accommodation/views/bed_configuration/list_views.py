from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accommodation.models.bed.bed_configuration import BedConfiguration
from apps.accommodation.views.base import BedConfigurationBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedConfigurationListView(BedConfigurationBaseView):
    template_name = "accommodation/bed_configuration/bed_configuration_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_view_bed_configurations(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view bed configurations."
                )
            )

        configurations = BedConfiguration.objects.all().order_by(
            "bed_count",
            "name",
        )

        paginator = Paginator(configurations, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "bed_configurations": page_obj.object_list,
                "page_obj": page_obj,
            },
        )