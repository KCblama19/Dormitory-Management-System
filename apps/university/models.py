from django.db import models
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel


"""
This Model represents the university operating this 
dormitory management system holds the University basic
information.

A single deployment is intended for one university, 
but the model supports multiple campuses, including campuses
located in different countries.
"""

class University(TimeStampModel):
    
    code = models.CharField(
        _("University Code"),
        max_length=20, 
        help_text=_("The code could be the abbreviation of the university name")       
    )
    name = models.CharField(
        _("University Name"),
        max_length=255,
        unique=True,
        blank=False,        
    )
    website = models.URLField(
        _("University Website"),
        blank=True
    )
    is_active = models.BooleanField(
        default=True
    )
    
    class Meta:
        ordering = ["-name"]
        verbose_name = "University"
        verbose_name_plural = "Universities"
    
    def __str__(self):
        return f"{self.name}"