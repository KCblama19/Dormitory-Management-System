
from django.shortcuts import redirect, render

from apps.accommodation.forms.bed_forms import CreateBedForm
from apps.accommodation.services.bed_service import BedService
from apps.accommodation.views.base import BuildingBaseView

from apps.core.exceptions import DomainError


class BedCreateView(BuildingBaseView):
    template_name = "accommodation/bed/bed_form.html"
    form_class = CreateBedForm

    def get_form(self, data=None):
        form = self.form_class(data)

        # Only rooms on operational floors in active buildings
        # should be offered for bed creation.
        form.fields["room"].queryset = (
            form.fields["room"].queryset
            .filter(
                floor__is_active=True,
                floor__status="ACTIVE",
                floor__building__is_active=True,
            )
            .select_related(
                "floor",
                "floor__building",
            )
            .order_by(
                "floor__building__building_number",
                "floor__floor_number",
                "position",
            )
        )

        return form

    def get(self, request, *args, **kwargs):
        form = self.get_form()

        return render(
            request,
            self.template_name,
            {"form": form.get_form()},
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form},
            )

        try:
            bed = BedService.create_bed(
                actor=request.user,
                room=form.cleaned_data["room"],
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return render(
                request,
                self.template_name,
                {"form": form},
            )

        self.add_success_message(
            f"Bed {bed.code} created successfully."
        )

        return redirect(
            "accommodation:bed-detail",
            pk=bed.pk,
        )
