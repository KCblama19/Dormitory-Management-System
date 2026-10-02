from django import forms

from apps.accommodation.models.building.building_model import Building
from apps.accommodation.models.campus.campus_model import Campus
from apps.accommodation.models.bed.bed_configuration import BedConfiguration

from apps.core.forms import StyledFormMixin


class BuildingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Building
        fields = (
            "campus",
            "building_number",
            "name",
            "code",
            "student_population",
            "gender_policy",
            "max_floors",
            "default_bed_configuration",
        )

    def clean_building_number(self):
        return self.cleaned_data["building_number"].strip()

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean_max_floors(self):
        max_floors = self.cleaned_data["max_floors"]

        if max_floors < 1:
            raise forms.ValidationError(
                "A building must allow at least one floor."
            )

        return max_floors


class ChangeBuildingGenderPolicyForm(StyledFormMixin, forms.Form):
    gender_policy = forms.ChoiceField(
        choices=Building.GenderPolicy.choices,
    )


class ChangeBuildingPopulationForm(StyledFormMixin, forms.Form):
    student_population = forms.ChoiceField(
        choices=Building.StudentPopulation.choices,
    )


class ChangeDefaultBedConfigurationForm(StyledFormMixin, forms.Form):
    bed_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
    )