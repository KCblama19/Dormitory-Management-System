from django import forms

# MODELS
from apps.accommodation.models.bed.bed_configuration import BedConfiguration

# SHARED UTILITY FORMS
from apps.core.forms import StyledFormMixin, OperationForm


class BedConfigurationForm(
    StyledFormMixin,
    forms.ModelForm,
):
    class Meta:
        model = BedConfiguration
        fields = (
            "name",
            "bed_count",
            "description",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 4},
            ),
        }

    def clean_bed_count(self):
        bed_count = self.cleaned_data["bed_count"]

        if bed_count < 2:
            raise forms.ValidationError(
                "A bed configuration must contain at least two beds."
            )

        return bed_count


class BedConfigurationStatusForm(OperationForm):
    bed_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.all(),
    )