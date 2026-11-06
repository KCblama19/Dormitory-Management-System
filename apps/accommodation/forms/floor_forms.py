from django import forms

# MODELS
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.bed.bed_configuration import BedConfiguration

# SHARE UTILITY FORM
from apps.core.forms import StyledFormMixin


class CreateFloorForm(StyledFormMixin, forms.Form):
    """
    Floor number is assigned by FloorService.

    The form collects the parent Building and initial configuration.
    """

    building = forms.ModelChoiceField(
        queryset=Building.objects.filter(is_active=True),
    )

    max_rooms_per_floor = forms.IntegerField(min_value=1)

    gender_configuration = forms.ChoiceField(
        choices=Floor.GenderConfiguration.choices,
        required=False,
    )

    bed_configuration_override = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
        required=False,
    )

    restriction_note = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    is_restricted = forms.BooleanField(required=False)


class FloorForm(StyledFormMixin, forms.ModelForm):
    """
    General editing form.

    Floor number, Building, operational status, restrictions, and
    bed configuration override are handled through dedicated operations.
    """

    class Meta:
        model = Floor
        fields = (
            "max_rooms_per_floor",
            "gender_configuration",
        )

    def clean_max_rooms_per_floor(self):
        value = self.cleaned_data["max_rooms_per_floor"]

        if value < 1:
            raise forms.ValidationError(
                "Maximum rooms per floor must be at least one."
            )

        return value


class ChangeFloorGenderForm(StyledFormMixin, forms.Form):
    gender_configuration = forms.ChoiceField(
        choices=Floor.GenderConfiguration.choices,
        required=False,
    )


class FloorRestrictionForm(StyledFormMixin, forms.Form):
    restriction_note = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class FloorBedConfigurationForm(StyledFormMixin, forms.Form):
    bed_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
        required=False,
    )