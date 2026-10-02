from django import forms

# MODELS
from apps.profiles.student.models.academic_year import AcademicYear

# SHARED UTILITY FORM
from apps.core.forms import StyledFormMixin, OperationForm


class AcademicYearForm(StyledFormMixin, forms.ModelForm):
    """
    Create or edit an academic year.

    Cross-field date validation is performed here for immediate user
    feedback. The model and database constraints remain authoritative.
    """

    class Meta:
        model = AcademicYear
        fields = (
            "name",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
        )
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date <= start_date:
            self.add_error(
                "end_date",
                "The end date must be after the start date.",
            )

        return cleaned_data


class SetAcademicYearCurrentForm(OperationForm):
    """
    Form for explicitly making an academic year current.
    """

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.active(),
    )