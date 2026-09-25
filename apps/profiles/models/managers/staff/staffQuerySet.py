from django.db import models


class StaffQuerySet(models.QuerySet):
    """
    QuerySet methods for Staff.

    Staff QuerySets provide reusable filtering and relationship loading.
    They do not perform staff-management operations.
    """

    def active(self):
        return self.filter(
            status="ACTIVE",
            user__is_active=True,
        )

    def inactive(self):
        return self.filter(
            models.Q(status="INACTIVE")
            | models.Q(user__is_active=False)
        )

    def managers(self):
        return self.filter(
            role="BUILDING_MANAGER",
        )

    def building_staff(self):
        return self.filter(
            role="BUILDING_STAFF",
        )

    def active_managers(self):
        return self.active().filter(
            role="BUILDING_MANAGER",
        )

    def active_building_staff(self):
        return self.active().filter(
            role="BUILDING_STAFF",
        )

    def for_building(self, building):
        building_id = getattr(building, "pk", building)

        return self.filter(
            building_id=building_id,
        )

    def active_for_building(self, building):
        return self.active().for_building(building)

    def managers_for_building(self, building):
        return (
            self.active_for_building(building)
            .filter(role="BUILDING_MANAGER")
        )

    def staff_for_building(self, building):
        return (
            self.active_for_building(building)
            .filter(role="BUILDING_STAFF")
        )

    def with_user(self):
        return self.select_related(
            "user",
        )

    def with_building(self):
        return self.select_related(
            "building",
            "building__campus",
            "building__campus__university",
        )

    def with_user_and_building(self):
        return self.select_related(
            "user",
            "building",
            "building__campus",
            "building__campus__university",
        )

    def search(self, term):
        return self.filter(
            models.Q(
                user__username__icontains=term,
            )
            | models.Q(
                user__first_name__icontains=term,
            )
            | models.Q(
                user__last_name__icontains=term,
            )
            | models.Q(
                user__email__icontains=term,
            )
            | models.Q(
                building__name__icontains=term,
            )
            | models.Q(
                building__building_number__icontains=term,
            )
        ).distinct()