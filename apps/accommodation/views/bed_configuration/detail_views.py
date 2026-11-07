from django.shortcuts import get_object_or_404, render

from apps.accommodation.models.bed.bed_configuration import BedConfiguration
from apps.accommodation.views.base import BedConfigurationBaseView

from apps.core.exceptions import PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedConfigurationDetailView(BedConfigurationBaseView):
    template_name = (
        "accommodation/bed_configuration/bed_configuration_detail.html"
    )

    def get(self, request, *args, **kwargs):
        configuration = get_object_or_404(
            BedConfiguration,
            pk=kwargs["pk"],
        )

        if not AccommodationPolicy.can_view_bed_configurations(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to view this bed configuration."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "bed_configuration": configuration,
            },
        )