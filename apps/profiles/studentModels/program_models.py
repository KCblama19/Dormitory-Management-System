from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

# Models and Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel
from apps.profiles.studentModels.degree_models import Degree
from apps.profiles.studentModels.major_models import Major

"""
This Model Tracks the University curriculum track, 
instruction language, and enrollment path a 
student applies for and studies.

    - Primary Function: Represents the exact 
      academic track a student applies to and enrolls 
      in (e.g., BSc Computer Science - English, 
      Chinese Language Program).

    - Key Features:
        - Categorization: Supports multiple program 
          types including degree-bearing tracks, 
          language study, exchange programs, and 
          visiting programs.
          
        - Tracks the primary language of instruction 
          (e.g., Chinese or English).
          
        - Flexible Attachments: Optional foreign keys 
          to Degree and Major. Degree programs 
          enforce both via clean(), 
          while language or exchange programs leave 
          them empty
"""

class Program(TimeStampModel):

    class ProgramType(models.TextChoices):
        DEGREE = "DEGREE", _("Degree Program")
        LANGUAGE = "LANGUAGE", _("Language Program")
        EXCHANGE = "EXCHANGE", _("Exchange Program")
        VISITING = "VISITING", _("Visiting Student Program")
        SHORT_TERM = "SHORT_TERM", _("Short-Term Program")
        OTHER = "OTHER", _("Other Program")

    class InstructionLanguage(models.TextChoices):
        CHINESE = "ZH", _("Chinese")
        ENGLISH = "EN", _("English")

    code = models.CharField(
        _("Program code"),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique institutional program code "
            "(e.g., 'BSC-CS-EN' or 'BSC-CS-ZH')."
        )
    )

    name = models.CharField(
        _("Program name"),
        max_length=255,
        help_text=_(
            "Full name of the academic program."
        )
    )

    program_type = models.CharField(
        _("Program type"),
        max_length=20,
        choices=ProgramType,
        help_text=_(
            "Type of program the student is enrolled in."
        )
    )

    instruction_language = models.CharField(
        _("Language of instruction"),
        max_length=2,
        choices=InstructionLanguage,
        help_text=_(
            "Language in which the program is taught."
        )
    )

    degree = models.ForeignKey(
        Degree,
        on_delete=models.PROTECT,
        related_name="programs",
        blank=True,
        null=True,
        help_text=_(
            "Degree associated with this program. "
            "Not required for non-degree programs."
        )
    )

    major = models.ForeignKey(
        Major,
        on_delete=models.PROTECT,
        related_name="programs",
        blank=True,
        null=True,
        help_text=_(
            "Major associated with this program. "
            "Not required for non-degree programs."
        )
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Program")
        verbose_name_plural = _("Programs")

    def clean(self):
        super().clean()

        # Degree programs must have a degree and a major.
        if self.program_type == self.ProgramType.DEGREE:

            if not self.degree:
                raise ValidationError({
                    "degree": _(
                        "A degree program must have a degree."
                    )
                })

            if not self.major:
                raise ValidationError({
                    "major": _(
                        "A degree program must have a major."
                    )
                })

            if not self.instruction_language:
                raise ValidationError({
                    "instruction_language": _(
                        "A degree program must specify "
                        "a language of instruction."
                    )
                })

        # Language programs normally do not belong to
        # a degree or academic major.
        if self.program_type == self.ProgramType.LANGUAGE:

            if self.degree:
                raise ValidationError({
                    "degree": _(
                        "A language program should not have "
                        "a degree assigned."
                    )
                })

            if self.major:
                raise ValidationError({
                    "major": _(
                        "A language program should not have "
                        "a major assigned."
                    )
                })

    def __str__(self):
        return f"{self.code}: {self.name}"
