from django import forms

# MODELS
from apps.accommodation.models import Room, BedConfiguration

# SHARE UTILITY FORMS
from apps.core.forms import StyledFormMixin, OperationForm


class InspectRoomConfigurationForm(OperationForm):
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )


class ExpandRoomForm(OperationForm):
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )

    target_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
    )


class PrepareRoomReductionForm(OperationForm):
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )

    target_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
    )


class ApplyRoomReductionForm(OperationForm):
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )

    target_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
    )


class ReconfigureRoomForm(OperationForm):
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
    )

    target_configuration = forms.ModelChoiceField(
        queryset=BedConfiguration.objects.active(),
    )