from django import forms

# MODELS
from apps.accommodation.models import Building
from apps.profiles.staff.models.staff_models import Staff

# SHARE UTILITY FORMS
from apps.core.forms import StyledFormMixin, OperationForm


class StaffForm(StyledFormMixin, forms.ModelForm):
    """
    Basic Staff profile data.

    This does not perform staff transfer, activation, or role changes.
    """

    class Meta:
        model = Staff
        fields = (
            "staff_id",
            "user",
            "building",
            "role",
            "status",
        )


class CreateStaffForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Staff
        fields = (
            "staff_id",
            "user",
            "building",
            "role",
        )


class AssignStaffToBuildingForm(OperationForm):
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.active(),
    )

    building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
    )


class ChangeStaffRoleForm(OperationForm):
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.active(),
    )

    role = forms.ChoiceField(
        choices=Staff.Role.choices,
    )


class StaffStatusForm(OperationForm):
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class TransferStaffForm(OperationForm):
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.active(),
    )

    new_building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )