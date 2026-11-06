from django import forms

# MODELS
from apps.accommodation.models.campus.campus_model import Campus

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
        )
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 4},
            ),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # A campus's parent university is selected only during creation.
        # Editing an existing campus must not change its parent.
        if self.instance and self.instance.pk:
            self.fields.pop("university")

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean_name(self):
        return self.cleaned_data["name"].strip()