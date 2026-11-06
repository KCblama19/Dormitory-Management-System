from apps.accommodation.models.bed.bed_configuration import (
    BedConfiguration,
)
from apps.accommodation.views.base import AccommodationDetailView
from apps.core.policies import AccommodationPolicy


class BedConfigurationDetailView(AccommodationDetailView):
    model = BedConfiguration
    template_name = "accommodation/bed_configuration/detail.html"
    context_object_name = "bed_configuration"

    def has_object_permission(self, obj):
        return AccommodationPolicy.can_view_bed_configurations(
            self.request.user
        )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                "default_for_buildings",
                "floor_overrides",
                "room_overrides",
            )
        )