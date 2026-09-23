from django.db import models

class RoomQuerySet(models.QuerySet):
    """
    Reusable queries for Room operations

    Assignment/occupancy-dependent queries will be added when the
    Assignment domain is implemented.
    """

    def for_floor(self, floor):
        floor_id = getattr(floor, "pk", floor)

        return self.filter(
            floor_id=floor_id,
        )

    def for_building(self, building):
        building_id = getattr(building, "pk", building)

        return self.filter(
            floor__building_id=building_id,
        )

    def with_floor(self):
        return self.select_related(
            "floor",
            "floor__building",
            "floor__building__campus",
        )

    def with_configuration(self):
        return self.select_related(
            "bed_configuration_override",
            "floor__bed_configuration_override",
            "floor__building__default_bed_configuration",
        )

    def with_beds(self):
        return self.prefetch_related(
            "beds",
        )

    def search(self, term):
        """
        Search using room position or the associated accommodation
        hierarchy.
        """
        return self.filter(
            models.Q(floor__floor_number__icontains=term)
            | models.Q(
                floor__building__building_number__icontains=term
            )
            | models.Q(
                floor__building__code__icontains=term
            )
        ).distinct()