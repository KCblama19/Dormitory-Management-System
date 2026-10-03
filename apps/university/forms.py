from django import forms

from apps.accommodation.models import University

from apps.core.forms import StyledFormMixin


class UniversityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = University
        fields = (
            "code",
            "name",
            "website",
            "is_active",
        )

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean_name(self):
        return self.cleaned_data["name"].strip()