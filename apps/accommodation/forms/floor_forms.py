from django import forms

# MODELS
from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.bed.bed_configuration import BedConfiguration

# SHARE UTILITY FORM
from apps.core.forms import StyledFormMixin


class FloorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Floor
        fields = (
            "building",
            "floor_number",
            "max_rooms_per_floor",
            "gender_configuration",
            "bed_configuration_override",
            "restriction_note",
            "status",
            "is_restricted",
        )
        widgets = {
            "restriction_note": forms.Textarea(
                attrs={"rows": 3},
            ),
        }

    def clean_floor_number(self):
        floor_number = self.cleaned_data["floor_number"]

        if floor_number < 1:
            raise forms.ValidationError(
                "Floor number must be a positive number."
            )

        return floor_number


class CreateFloorForm(StyledFormMixin, forms.Form):
    """
    Floor creation does not ask the user for floor_number because the
    FloorService determines the next available physical floor number.
    """

    building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
    )

    max_rooms_per_floor = forms.IntegerField(
        min_value=1,
    )

    gender_configuration = forms.ChoiceField(
        choices=Floor.GenderConfiguration.choices,
    )

    bed_configuration_override = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
        required=False,
    )

    restriction_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    is_restricted = forms.BooleanField(
        required=False,
    )


class ChangeFloorGenderForm(StyledFormMixin, forms.Form):
    gender_configuration = forms.ChoiceField(
        choices=Floor.GenderConfiguration.choices,
    )


class FloorRestrictionForm(StyledFormMixin, forms.Form):
    restriction_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class FloorBedConfigurationForm(StyledFormMixin, forms.Form):
    bed_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
        required=False,
    )