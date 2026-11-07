from django.shortcuts import redirect, render

from apps.accommodation.forms.bed_configuration_forms import (
    BedConfigurationForm,
)
from apps.accommodation.services.bed_config_service import (
    BedConfigurationService,
)
from apps.accommodation.views.base import BedConfigurationBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedConfigurationCreateView(BedConfigurationBaseView):
    template_name = (
        "accommodation/bed_configuration/bed_configuration_form.html"
    )

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_bed_configuration(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create bed configurations."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": BedConfigurationForm(),
                "page_title": "Create Bed Configuration",
                "submit_label": "Create Configuration",
            },
        )

    def post(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_bed_configuration(request.user):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create bed configurations."
                )
            )

        form = BedConfigurationForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Bed Configuration",
                    "submit_label": "Create Configuration",
                },
            )

        data = form.cleaned_data

        try:
            configuration = BedConfigurationService.create_configuration(
                actor=request.user,
                name=data["name"],
                bed_count=data["bed_count"],
                description=data["description"],
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Bed Configuration",
                    "submit_label": "Create Configuration",
                },
            )

        self.add_success_message(
            "Bed configuration created successfully."
        )

        return redirect(
            "accommodation:bed-configuration-detail",
            pk=configuration.pk,
        )