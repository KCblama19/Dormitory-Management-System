from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodations.forms.bed_configuration_forms import (
    BedConfigurationForm,
)
from apps.accommodations.models.bed.bed_configuration import BedConfiguration
from apps.accommodations.services.bed_config_service import (
    BedConfigurationService,
)
from apps.accommodations.views.base import BedConfigurationBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class BedConfigurationUpdateView(BedConfigurationBaseView):
    template_name = (
        "accommodation/bed_configuration/bed_configuration_form.html"
    )

    def get_configuration(self):
        return get_object_or_404(
            BedConfiguration,
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        configuration = self.get_configuration()

        if not AccommodationPolicy.can_update_bed_configuration(
            request.user,
            configuration,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this bed configuration."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "form": BedConfigurationForm(instance=configuration),
                "bed_configuration": configuration,
                "page_title": "Update Bed Configuration",
                "submit_label": "Save Changes",
            },
        )

    def post(self, request, *args, **kwargs):
        configuration = self.get_configuration()

        if not AccommodationPolicy.can_update_bed_configuration(
            request.user,
            configuration,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this bed configuration."
                )
            )

        form = BedConfigurationForm(
            request.POST,
            instance=configuration,
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "bed_configuration": configuration,
                    "page_title": "Update Bed Configuration",
                    "submit_label": "Save Changes",
                },
            )

        editable_fields = {
            "name",
            "bed_count",
            "description",
        }

        changes = {
            field: form.cleaned_data[field]
            for field in form.changed_data
            if field in editable_fields
        }

        try:
            updated_configuration = (
                BedConfigurationService.update_configuration(
                    actor=request.user,
                    configuration=configuration,
                    **changes,
                )
            )

        except DomainError as error:
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "bed_configuration": configuration,
                    "page_title": "Update Bed Configuration",
                    "submit_label": "Save Changes",
                },
            )

        self.add_success_message(
            "Bed configuration updated successfully."
        )

        return redirect(
            "accommodation:bed-configuration-detail",
            pk=updated_configuration.pk,
        )


class BedConfigurationStateChangeView(BedConfigurationBaseView):
    template_name = (
        "accommodation/bed_configuration/"
        "bed_configuration_confirm_operation.html"
    )

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    def get_configuration(self):
        return get_object_or_404(
            BedConfiguration,
            pk=self.kwargs["pk"],
        )

    def is_authorized(self, actor, configuration):
        policy = getattr(AccommodationPolicy, self.policy_method)
        return policy(actor, configuration)

    def get(self, request, *args, **kwargs):
        configuration = self.get_configuration()

        if not self.is_authorized(request.user, configuration):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to perform this operation."
                )
            )

        return render(
            request,
            self.template_name,
            {
                "bed_configuration": configuration,
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        configuration = self.get_configuration()

        if not self.is_authorized(request.user, configuration):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to perform this operation."
                )
            )

        service = getattr(BedConfigurationService, self.service_method)

        try:
            service(
                actor=request.user,
                configuration=configuration,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:bed-configuration-detail",
                pk=configuration.pk,
            )

        self.add_success_message(self.success_message)

        return redirect(
            "accommodation:bed-configuration-detail",
            pk=configuration.pk,
        )


class BedConfigurationActivateView(BedConfigurationStateChangeView):
    operation_label = "Activate Bed Configuration"
    success_message = "Bed configuration activated successfully."
    policy_method = "can_activate_bed_configuration"
    service_method = "activate_configuration"


class BedConfigurationDeactivateView(BedConfigurationStateChangeView):
    operation_label = "Deactivate Bed Configuration"
    success_message = "Bed configuration deactivated successfully."
    policy_method = "can_deactivate_bed_configuration"
    service_method = "deactivate_configuration"