from django.db import models

class BedConfigurationQuerySet(models.QuerySet):
    """
    Reusable queries for BedConfiguration
    operations
    """

    def active(self):
        return self.filter(
            is_active=True,
        )

    def inactive(self):
        return self.filter(
            is_active=False,
        )

    def for_bed_count(self, bed_count):
        return self.filter(
            bed_count=bed_count,
        )

    def with_bed_count_at_least(self, minimum):
        return self.filter(
            bed_count__gte=minimum,
        )

    def with_bed_count_at_most(self, maximum):
        return self.filter(
            bed_count__lte=maximum,
        )

    def search(self, term):
        return self.filter(
            models.Q(name__icontains=term)
            | models.Q(description__icontains=term)
        )