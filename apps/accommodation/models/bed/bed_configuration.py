from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract models
from apps.abstract_models.timestamp_models import TimeStampModel

# Manager
from apps.accommodation.models.managers.bedConfigQuerySet import BedConfigurationQuerySet


class BedConfiguration(TimeStampModel):
    """
    Defines a reusable accommodation configuration for rooms capacity
    
    A BedConfiguration describes how many beds a room
    is intended to contain. It does not represent the 
    physical beds themselves.
    
    Configuration inheritance:
        - Building default
              |
        - Floor override
              |
        - Room override
        
    The actual physical Bed records remain the source 
    of truth existing accommodation units.
    
    """
    
    
    name = models.CharField(
        _("Configuration name"),
        max_length=100,
        unique=True,
        help_text=_(
            "Human-readable name for this accommodation configuration"
            "e.g., '2-Bed Room", '4-Bed Room'
        ),
    )
    
    bed_count = models.PositiveSmallIntegerField(
        _("Bed count"),
        help_text=_(
            "Number of physical beds intended for a "
            "room using this configuration."
        ),
    )
    
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_(
            "Optional description of this "
            "accommodation configuration"
        ),
    )
    is_active = models.BooleanField(
        _("Configuration Status"),
        default=True,
        help_text=_(
            "Whether this configuration is currently"
            "for use"
        ),
    )
    
    objects = BedConfigurationQuerySet.as_manager()
    
    class Meta:
        ordering = ["bed_count", "name"]
        verbose_name = _("Bed Configuration")
        verbose_name_plural = _("Bed Configurations")
        
        constraint = [
            models.CheckConstraint(
                condition=Q(bed_count__gte=1),
                name="bed_configuration_count_gte_1",
            ),
        ]
        
    def clean(self):
        super().clean()
            
        if self.bed_count <= 1:
            raise ValidationError(
                {
                    "bed_count": _(
                        "A bed configuration must"
                        "contain at least one bed"
                    )
                }
            )
    def __str__(self):
        return f"{self.name} ({self.bed_count} beds)"
                
            