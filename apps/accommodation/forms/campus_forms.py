from django import forms

# MODELS
from apps.accommodation.models.campus.campus_model import Campus
from apps.university.models import University

# SHARE UTILITY FORMS
from apps.core.forms import StyledFormMixin


class CampusForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Campus
        fields = (
            "university",
            "name",
            "code",
            "postal_code",
            "address",
            "city",
            "province",
            "country",
            "description",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 4},
            ),
        }

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean_name(self):
        return self.cleaned_data["name"].strip()