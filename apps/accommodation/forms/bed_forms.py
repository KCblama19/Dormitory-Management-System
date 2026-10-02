from django import forms

# MODELS
from apps.accommodation.models.bed.bed_model import Bed 
from apps.accommodation.models.room.room_model import Room

# SHARE UTILITY FORM
from apps.core.forms import StyledFormMixin, OperationForm


class BedForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Bed
        fields = (
            "room",
            "position",
            "status",
        )

    def clean_position(self):
        position = self.cleaned_data["position"]

        if position < 1:
            raise forms.ValidationError(
                "Bed position must be at least 1."
            )

        return position


class CreateBedForm(StyledFormMixin, forms.Form):
    """
    Bed position is determined by the BedService.

    The form therefore does not ask the user for a position.
    """

    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )


class UpdateBedPositionForm(OperationForm):
    bed = forms.ModelChoiceField(
        queryset=Bed.objects.all(),
    )

    position = forms.IntegerField(
        min_value=1,
    )


class SetBedStatusForm(OperationForm):
    bed = forms.ModelChoiceField(
        queryset=Bed.objects.all(),
    )

    status = forms.ChoiceField(
        choices=Bed.Status.choices,
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )