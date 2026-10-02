from django import forms

# MODELS
from apps.profiles.student.models.academic_year import AcademicYear
from apps.profiles.student.models.student_models import Student
from apps.profiles.student.models.enrollment import StudentEnrollment
from apps.profiles.student.models.program import Program

# SHARE UTILITY FORMS
from apps.core.forms import StyledFormMixin, OperationForm


class EnrollmentForm(StyledFormMixin, forms.ModelForm):
    """
    Creates or edits enrollment data.

    Enrollment lifecycle transitions remain service operations.
    """

    class Meta:
        model = StudentEnrollment
        fields = (
            "student",
            "program",
            "academic_year",
            "is_primary",
            "year_of_study",
            "enrollment_status",
            "start_date",
            "end_date",
            "expected_graduation_date",
        )
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "expected_graduation_date": forms.DateInput(
                attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        graduation_date = cleaned_data.get(
            "expected_graduation_date"
        )

        if start_date and end_date and end_date <= start_date:
            self.add_error(
                "end_date",
                "The end date must be after the start date.",
            )

        if (
            start_date
            and graduation_date
            and graduation_date <= start_date
        ):
            self.add_error(
                "expected_graduation_date",
                "Expected graduation must be after the enrollment start date.",
            )

        enrollment_status = cleaned_data.get("enrollment_status")
        is_primary = cleaned_data.get("is_primary")

        if is_primary and enrollment_status != "ACTIVE":
            self.add_error(
                "is_primary",
                "Only an active enrollment can be primary.",
            )

        return cleaned_data


class CreateEnrollmentForm(EnrollmentForm):
    """
    Explicit creation form.

    The queryset restrictions can be tightened by the view based on
    the actor's authorization scope.
    """

    pass


class EnrollmentActionForm(OperationForm):
    student_enrollment = forms.ModelChoiceField(
        queryset=StudentEnrollment.objects.all(),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class SetPrimaryEnrollmentForm(OperationForm):
    student_enrollment = forms.ModelChoiceField(
        queryset=StudentEnrollment.objects.all(),
    )