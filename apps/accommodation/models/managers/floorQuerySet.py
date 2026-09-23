from django.db import models

class FloorQuerySet(models.QuerySet):
    """
    Reusable queries for floor operations
    """

    def active(self):
        return self.filter(
            status="ACTIVE",
        )

    def inactive(self):
        return self.filter(
            status="INACTIVE",
        )

    def maintenance(self):
        return self.filter(
            status="MAINTENANCE",
        )

    def restricted(self):
        return self.filter(
            is_restricted=True,
        )

    def unrestricted(self):
        return self.filter(
            is_restricted=False,
        )

    def for_building(self, building):
        building_id = getattr(building, "pk", building)

        return self.filter(
            building_id=building_id,
        )

    def male(self):
        return self.filter(
            gender_configuration="MALE",
        )

    def female(self):
        return self.filter(
            gender_configuration="FEMALE",
        )

    def mixed(self):
        return self.filter(
            gender_configuration="MIXED",
        )

    def with_building(self):
        return self.select_related(
            "building",
            "building__campus",
        )

    def with_configuration(self):
        return self.select_related(
            "bed_configuration_override",
            "building__default_bed_configuration",
        )