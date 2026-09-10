from django.db import models
from apps.abstract_models.timestamp_models import TimeStampModel
from django.utils.translation import gettext_lazy as _

class Gender(TimeStampModel):
    
    class GenderType(models.TextChoices):
        MALE = "M", _("Male"),
        FEMALE = "F", _("Female")
        
        
    code = models.CharField(
        _("Gender Abbreviation"),
        max_length=3,
        choices=GenderType,
        unique=True,
    )
    name = models.CharField(
        max_length=20,
        unique=True,
    )
    is_active = models.BooleanField(
        default=True,
    )
    
    class Meta:
        abstract = True