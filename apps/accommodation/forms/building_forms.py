from django import forms
from django.db.models import Q

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # A building belongs to its original campus. Campus selection is
        # therefore only available when creating a new building.
        if self.instance and self.instance.pk:
            self.fields.pop("campus")

        else:
            self.fields["campus"].queryset = Campus.objects.filter(
                is_active=True
            )

        # New buildings must use an active configuration. When editing,
        # retain the current configuration as an option even if inactive.
        configuration_queryset = BedConfiguration.objects.filter(
            is_active=True
        )

        if self.instance and self.instance.pk:
            configuration_queryset = (
                BedConfiguration.objects.filter(
                    Q(is_active=True)
                    | Q(pk=self.instance.default_bed_configuration_id)
                )
            )

        self.fields["default_bed_configuration"].queryset = (
            configuration_queryset
        )

    def clean_name(self):
        return self.cleaned_data["name"].strip()

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
    default_bed_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.filter(is_active=True),
    )