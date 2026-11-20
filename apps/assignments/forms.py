from django import forms
from django.forms import BaseFormSet, formset_factory
from django.core import signing

from apps.accommodations.models import Bed, Building
from apps.profiles.student.models.student_models import Student


class AllocationScheduleForm(forms.Form):
    """Collect the building and reservation schedule shared by an allocation."""

    building_id = forms.ModelChoiceField(queryset=Building.objects.none())
    expected_check_in = forms.DateField(input_formats=["%Y-%m-%d"])
    check_in_deadline = forms.DateField(input_formats=["%Y-%m-%d"])
    expected_check_out = forms.DateField(
        input_formats=["%Y-%m-%d"],
        required=False,
    )
    grace_period_days = forms.IntegerField(min_value=0, required=False)
    notes = forms.CharField(required=False)

    def __init__(self, *args, buildings, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building_id"].queryset = buildings

    def clean_grace_period_days(self):
        days = self.cleaned_data["grace_period_days"]
        return 0 if days is None else days


class AutomaticAllocationForm(AllocationScheduleForm):
    """Collect the student for an individual automatic allocation."""

    student_id = forms.ModelChoiceField(queryset=Student.objects.all())


class GroupAllocationOptionsForm(AllocationScheduleForm):
    """Record the group's consent to partial allocation."""

    allow_partial = forms.BooleanField(
        label="The group has agreed to partial allocation",
        required=False,
    )


class AllocationStudentsForm(GroupAllocationOptionsForm):
    """Collect one or more students for a recommendation."""

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.order_by("pk"),
    )


class AutomaticGroupAllocationForm(AllocationStudentsForm):
    """Require at least two students for automatic group allocation."""

    def clean_students(self):
        students = self.cleaned_data["students"]

        if len(students) < 2:
            raise forms.ValidationError("Select at least two students.")

        return students


class ManualAllocationRowForm(forms.Form):
    """Record a group member and the bed staff propose for that member."""

    student = forms.ModelChoiceField(queryset=Student.objects.all())
    bed = forms.ModelChoiceField(queryset=Bed.objects.none(), required=False)

    def __init__(self, *args, beds, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bed"].queryset = beds


class BaseManualAllocationFormSet(BaseFormSet):
    """Validate student and bed selections across the submitted rows."""

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        seen_students = set()
        seen_beds = set()

        for row in self.forms:
            if not row.cleaned_data:
                continue

            student = row.cleaned_data["student"]
            bed = row.cleaned_data["bed"]

            if student.pk in seen_students:
                row.add_error("student", "This student is already listed.")
            seen_students.add(student.pk)

            if bed is not None:
                if bed.pk in seen_beds:
                    row.add_error("bed", "This bed has already been selected.")
                seen_beds.add(bed.pk)

        if not seen_beds:
            raise forms.ValidationError("Select at least one bed.")


ManualAllocationFormSet = formset_factory(
    ManualAllocationRowForm,
    formset=BaseManualAllocationFormSet,
    min_num=1,
    validate_min=True,
    extra=0,
)


class AssignmentCheckInForm(forms.Form):
    """Record whether staff approve an early arrival."""

    approve_early = forms.TypedChoiceField(
        choices=(("true", "Approve early arrival"), ("false", "Normal check-in")),
        coerce=lambda value: value == "true",
        empty_value=False,
        required=False,
    )


class ReservationCancellationForm(forms.Form):
    """Require the reason recorded by the reservation cancellation service."""

    reason = forms.CharField()


class AssignmentExtensionRequestForm(forms.Form):
    """Collect the later check-in deadline requested by the student."""

    requested_check_in_deadline = forms.DateField(input_formats=["%Y-%m-%d"])
    reason = forms.CharField(required=False)


class CheckoutRequestForm(forms.Form):
    """Collect the student's preferred checkout date."""

    requested_checkout_date = forms.DateField(input_formats=["%Y-%m-%d"])
    reason = forms.CharField(required=False)


class WorkflowDecisionForm(forms.Form):
    """Require an explicit approval or rejection from the reviewer."""

    approve = forms.TypedChoiceField(
        label="Decision",
        choices=(("approve", "Approve"), ("reject", "Reject")),
        coerce=lambda value: value == "approve",
    )
    decision_note = forms.CharField(required=False)


class CheckoutDecisionForm(WorkflowDecisionForm):
    """Require verified physical departure before approving checkout."""

    departure_confirmed = forms.TypedChoiceField(
        choices=(("yes", "Departure confirmed"), ("no", "Not confirmed")),
        coerce=lambda value: value == "yes",
        empty_value=False,
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("approve") and not cleaned_data.get("departure_confirmed"):
            self.add_error(
                "departure_confirmed",
                "Confirm that the student has departed before approving checkout.",
            )

        return cleaned_data


class TransferRequestForm(forms.Form):
    """Collect a destination bed, a reason, and the preferred move date."""

    destination_bed = forms.ModelChoiceField(queryset=Bed.objects.none())
    reason = forms.CharField()
    requested_move_date = forms.DateField(
        input_formats=["%Y-%m-%d"],
        required=False,
    )

    def __init__(self, *args, destination_beds, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination_bed"].queryset = destination_beds


class TransferDecisionForm(forms.Form):
    """Require an approved move date when the reviewer accepts the transfer."""

    approve = forms.TypedChoiceField(
        label="Decision",
        choices=(("approve", "Approve"), ("reject", "Reject")),
        coerce=lambda value: value == "approve",
    )
    approved_move_date = forms.DateField(
        input_formats=["%Y-%m-%d"],
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("approve") and not cleaned_data.get("approved_move_date"):
            self.add_error("approved_move_date", "Enter the approved move date.")

        return cleaned_data


class TransferCompletionForm(AssignmentCheckInForm):
    """Record that the student has physically completed the move."""

    move_confirmed = forms.TypedChoiceField(
        label="Physical move",
        choices=(("yes", "The student has moved"),),
        coerce=lambda value: value == "yes",
    )


class TransferCancellationRequestForm(forms.Form):
    """Collect the student's reason for asking to cancel the transfer."""

    reason = forms.CharField()


class TransferCancellationForm(forms.Form):
    """Allow staff to add a reason when carrying out a cancellation."""

    reason = forms.CharField(required=False)


class AssignmentEligibilityDecisionForm(forms.Form):
    """Collect the manager's decision on a pending eligibility review."""

    approve = forms.TypedChoiceField(
        label="Eligibility decision",
        choices=(("approve", "Approve"), ("reject", "Reject")),
        coerce=lambda value: value == "approve",
    )


class AssignmentTerminationForm(forms.Form):
    """Record why the stay is ending and confirm the student has departed."""

    reason = forms.CharField(label="Reason for termination", widget=forms.Textarea)
    departure_confirmed = forms.TypedChoiceField(
        label="Physical departure",
        choices=(("yes", "The student has physically departed"),),
        coerce=lambda value: value == "yes",
    )
    
class AllocationProposalApprovalForm(forms.Form):
    """Carry the exact bed selections shown on the approval page."""

    snapshot = forms.CharField(widget=forms.HiddenInput)
    snapshot_salt = "assignments.allocation-proposal-approval"

    def __init__(self, *args, allocation_request, **kwargs):
        super().__init__(*args, **kwargs)
        self.allocation_request = allocation_request

    @classmethod
    def make_snapshot(cls, allocation_request, members):
        """Sign the reviewed selections and bind them to this request."""
        return signing.dumps(
            {
                "request_id": str(allocation_request.pk),
                "selections": [
                    [str(member.student_id), str(member.assigned_bed_id)]
                    for member in members
                ],
            },
            salt=cls.snapshot_salt,
        )

    def clean_snapshot(self):
        try:
            payload = signing.loads(
                self.cleaned_data["snapshot"],
                salt=self.snapshot_salt,
            )
        except signing.BadSignature as exc:
            raise forms.ValidationError(
                "The approval form is invalid. Reload the proposal and review it again."
            ) from exc

        if payload["request_id"] != str(self.allocation_request.pk):
            raise forms.ValidationError(
                "This approval form belongs to another allocation request."
            )

        if not payload["selections"]:
            raise forms.ValidationError("There are no proposed beds to approve.")

        # The service compares the reviewed IDs with the saved IDs, so use
        # the actual model field types when reading the signed selections.
        return {
            Student._meta.pk.to_python(student_id): Bed._meta.pk.to_python(bed_id)
            for student_id, bed_id in payload["selections"]
        }


class ManualAllocationRevisionForm(forms.Form):
    """Let staff replace bed choices for the request's unfinished members."""

    def __init__(self, *args, members, beds, **kwargs):
        super().__init__(*args, **kwargs)
        self.members = members

        # The server supplies the members. The submitted form only chooses
        # a bed for each of those members.
        for member in members:
            self.fields[f"bed_{member.pk}"] = forms.ModelChoiceField(
                label=str(member.student),
                queryset=beds,
                initial=member.assigned_bed_id,
                required=False,
            )

    def selected_beds_by_student(self):
        """Return the replacement mapping expected by AllocationService."""
        selections = {}

        for member in self.members:
            bed = self.cleaned_data[f"bed_{member.pk}"]
            if bed is not None:
                selections[member.student_id] = bed.pk

        return selections
    
class AllocationResolutionForm(forms.Form):
    """Collect an optional reason for closing an unfinished allocation."""

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )