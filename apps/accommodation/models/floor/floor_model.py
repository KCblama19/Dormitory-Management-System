from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel

class Floor(TimeStampModel):
    class GenderConfiguration(models.TextChoices):
        MALE = "MALE", _("Male")
        FEMALE = "FEMALE", _("Female")
        MIXED = "MIXED", _("Mixed")
        
    class FloorStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        INACTIVE = "INACTIVE", _("Inactive")
        MAINTENANCE = "MAINTENANCE", _("Maintenance")
                
    building = models.ForeignKey(
        "accommodation.Building",
        on_delete=models.CASCADE,
        related_name="floors",
        verbose_name=_("building"),
    )
    floor_number = models.PositiveSmallIntegerField(
        _("floor number"),
        validators=[MinValueValidator(1)],
        help_text=_("Dormitory building floor number")
    )
    max_rooms_per_floor = models.PositiveSmallIntegerField(
        _("Maximum Rooms"),
        validators=[MinValueValidator(1)],
        help_text=_("Maximum number of rooms on each floor")
    )
    gender_configuration = models.CharField(
        _("Gender Configuration"),
        choices=GenderConfiguration.choices,
        null=True,
        blank=True,
        help_text=_("Optional floor level gender configuration"
                    "Only applicable if the gender policy of the building is Mixed"
        ),
    )
    default_floor_bed_capacity = models.PositiveSmallIntegerField(
        _("Default floor bed capacity"),
        validators=[MinValueValidator(1)],
        null=True,
        blank=True,
        help_text=_("Optional floor level bed configuration"
                    "If not set, the floor inherit the default bed capacity of the building")
    )
    restriction_note = models.TextField(
        max_length=255,
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("Floor Status"),
        max_length=20,
        choices=FloorStatus.choices,
        default=FloorStatus.ACTIVE,
        help_text=_("The current floor status")
    )
    # If floor is restricted or preserved for professors or staffs
    is_restricted = models.BooleanField(
        _("Floor Restriction"),
        default=False,
        help_text=_("Show the floor is restricted or preserve for professors or staff")
    )
    
    class Meta:
        ordering = ["building", "floor_number"]
        indexes = [
            models.Index(
                fields=["building", "status"]
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["building", "floor_number"],
                name="unique_floor_number_per_building",
            ),
        ]
    
    def __str__(self):
        return f"{self.building} Floor {self.building_number}"
    