from django import forms

from apps.accommodation.models import Campus
from apps.profiles.student.models.academic_year import AcademicYear
from apps.profiles.student.models.student_models import Student
from apps.profiles.student.models.campus_assignment import StudentAssignCampus

from apps.core.forms import StyledFormMixin, OperationForm


class CampusAssignmentForm(
    StyledFormMixin,
    forms.ModelForm,
):
    class Meta:
        model = StudentAssignCampus
        fields = (
            "student",
            "campus",
            "academic_year",
            "campus_arrival_date",
            "start_date",
            "end_date",
            "status",
            "reason",
        )
        widgets = {
            "campus_arrival_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "start_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "reason": forms.Textarea(
                attrs={"rows": 3},
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


class AssignStudentCampusForm(OperationForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
    )

    campus = forms.ModelChoiceField(
        queryset=Campus.objects.active(),
    )

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.active(),
    )

    campus_arrival_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class TransferStudentCampusForm(OperationForm):
    student_assignment = forms.ModelChoiceField(
        queryset=StudentAssignCampus.objects.active(),
    )

    new_campus = forms.ModelChoiceField(
        queryset=Campus.objects.active(),
    )

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )


class EndCampusAssignmentForm(OperationForm):
    student_assignment = forms.ModelChoiceField(
        queryset=StudentAssignCampus.objects.active(),
    )

    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )