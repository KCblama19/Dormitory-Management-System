
from django.db import models


class BedQuerySet(models.QuerySet):
    """
    Reusable queries for Bed operations.

    Occupancy-dependent methods will be added only after the
    Assignment model exists.
    """

    def with_configuration(self):
        return self.select_related(
            "room",
            "room__bed_configuration_override",
            "room__floor",
            "room__floor__bed_configuration_override",
            "room__floor__building",
            "room__floor__building__default_bed_configuration",
        )

    def highest_position_for_room(self, room):
        room_id = getattr(room, "pk", room)

        return self.filter(
            room_id=room_id,
        ).aggregate(
            highest_position=models.Max("position"),
        )["highest_position"]

    def available(self):
        return self.filter(
            status=self.model.Status.AVAILABLE,
        )

    def maintenance(self):
        return self.filter(
            status=self.model.Status.MAINTENANCE,
        )

    def out_of_service(self):
        return self.filter(
            status=self.model.Status.OUT_OF_SERVICE,
        )

    def operational(self):
        """
        Return beds that are not permanently out of service.

        Maintenance beds still physically exist, so they count
        toward physical capacity but are not currently available.
        """
        return self.exclude(
            status__in=[
                self.model.Status.OUT_OF_SERVICE,
                self.model.Status.RETIRED,
            ]
        )

    def for_room(self, room):
        room_id = getattr(room, "pk", room)

        return self.filter(
            room_id=room_id,
        )

    def for_floor(self, floor):
        floor_id = getattr(floor, "pk", floor)

        return self.filter(
            room__floor_id=floor_id,
        )

    def for_building(self, building):
        building_id = getattr(building, "pk", building)

        return self.filter(
            room__floor__building_id=building_id,
        )

    def with_room(self):
        return self.select_related(
            "room",
            "room__floor",
            "room__floor__building",
        )

    def with_hierarchy(self):
        return self.select_related(
            "room",
            "room__floor",
            "room__floor__building",
            "room__floor__building__campus",
        )