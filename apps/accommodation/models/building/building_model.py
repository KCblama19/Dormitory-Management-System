from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

# Manager
from apps.accommodation.models.managers.buildingQuerySet import BuildingQuerySet

class Building(TimeStampModel):
    class StudentPopulation(models.TextChoices):
        INTERNATIONAL = "INTERNATIONAL", _("International")
        CHINESE = "CHINESE", _("Chinese")
        
    class GenderPolicy(models.TextChoices):
        MALE_ONLY = "MALE ONLY", _("Male Only")
        FEMALE_ONLY = "FEMALE ONLY", _("Female Only")
        MIXED = "MIXED", _("mixed")
    
    campus = models.ForeignKey(
        "accommodation.Campus",
        on_delete=models.PROTECT,
        related_name="buildings",
    )
    building_number = models.CharField(
        _("Building Number"),
        max_length=32,
        help_text=_("Number of the building")
    )
    name = models.CharField(
        _("Building Name"),
        max_length=255,
        help_text=_("Name of the building")
        
    )
    code = models.CharField(
        _("Building Code"),
        max_length=20,
        help_text=_("This holds the unique building code")
    )
    student_population = models.CharField(
        _("Student Population"),
        choices=StudentPopulation.choices,
        help_text=_("Determines whether this building accommodates international "
                   "or Chinese students."
        ),
    )
    gender_policy = models.CharField(
        _("Gender Policy"),
        choices=GenderPolicy.choices,
        help_text=_("Determines whether this building accommodates a specific gender "
                   "or Mixed genders."
        ),
    )
    max_floors = models.PositiveSmallIntegerField(
        _("Maximum Floors"),
        help_text=_("The maximum number of floors of the building."),
    )
    default_bed_configuration = models.ForeignKey(
        "accommodation.BedConfiguration",
        on_delete=models.PROTECT,
        related_name="default_for_buildings",
        verbose_name=_("default bed configuration"),
        help_text=_(
            "Default number of physical beds in each room"
            "in this building."
        ),
    )
    
    is_active = models.BooleanField(
        default=True,
    )
    
    class Meta:
        ordering = ["campus", "building_number"]
        verbose_name = _("Building")
        verbose_name_plural = _("Buildings")
        
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "building_number"],
                name = "unique_building_number_per_campus",
            ),
            models.UniqueConstraint(
                fields=["campus", "code"],
                name="unique_building_code_per_campus",
            ),
            models.CheckConstraint(
                condition=Q(max_floors__gte=1),
                name="max_floor_cannot_be_less_than_one",
            ),
        ]
        
    objects = BuildingQuerySet.as_manager()
    
    def __str__(self):
        return f"{self.name} | Bul-{self.building_number}"
    