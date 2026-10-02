from django import forms

from apps.profiles.student.models.student_models import Student
from apps.core.forms import StyledFormMixin, OperationForm


class StudentForm(StyledFormMixin, forms.ModelForm):
    """
    Basic student profile form.

    This form does not perform admission, eligibility, or account
    activation operations.
    """

    class Meta:
        model = Student
        fields = (
            "student_id",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "nationality",
            "admission_status",
            "eligibility_status",
            "bio",
        )
        widgets = {
            "bio": forms.Textarea(
                attrs={"rows": 4},
            ),
        }

    def clean_student_id(self):
        student_id = self.cleaned_data["student_id"].strip()

        if not student_id:
            raise forms.ValidationError(
                "Student ID cannot be empty."
            )

        return student_id


class AcceptStudentForm(OperationForm):
    """
    Form used when an authorized actor accepts a student.
    """

    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )


class RejectStudentForm(OperationForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class WithdrawStudentForm(OperationForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class SetStudentEligibilityForm(OperationForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )

    eligibility_status = forms.ChoiceField(
        choices=Student.EligibilityStatus.choices,
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class StudentAccountActionForm(OperationForm):
    """
    Used by account activation/deactivation/suspension workflows.
    """

    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )