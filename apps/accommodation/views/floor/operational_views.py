
from django.shortcuts import get_object_or_404, redirect, render

from apps.accommodation.models.floor.floor_model import Floor
from apps.accommodation.services.floor_service import FloorService
from apps.accommodation.views.building.base import BuildingBaseView

from apps.accommodation.forms.floor.floor_forms import (
    FloorRestrictionForm,
    FloorBedConfigurationForm,
)

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


# ============================================================
# BASE FLOOR OPERATION VIEW
# ============================================================

class FloorOperationBaseView(BuildingBaseView):
    """
    Shared functionality for floor operational views.

    Operational views:
        - Change floor status.
        - Manage floor restrictions.
        - Manage bed-configuration overrides.

    Each operation retains its own policy and service method.
    """

    def get_floor(self):
        """
        Retrieve the floor together with its building.

        The building is required by floor policies and services.
        """
        return get_object_or_404(
            Floor.objects.select_related("building"),
            pk=self.kwargs["pk"],
        )

    def is_authorized(self, actor, floor, policy_method):
        """
        Execute the operation-specific authorization policy.
        """
        policy = getattr(AccommodationPolicy, policy_method)

        return policy(actor, floor)

    def check_operation_permission(
        self,
        request,
        floor,
        policy_method,
    ):
        """
        Check permission before displaying or executing an operation.

        Returns True when authorized.
        """
        if self.is_authorized(
            request.user,
            floor,
            policy_method,
        ):
            return True

        self.handle_domain_error(
            PermissionDenied(
                "You do not have permission to perform this operation."
            )
        )

        return False


# ============================================================
# FLOOR STATUS OPERATIONS
# ============================================================

class FloorStateChangeView(FloorOperationBaseView):
    """
    Base view for operations that change floor status.

    Examples:
        - Activate.
        - Deactivate.
        - Set maintenance.

    These operations do not require additional form data.
    """

    template_name = "accommodation/floor/floor_confirm_operation.html"

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    def get(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        return render(
            request,
            self.template_name,
            {
                "floor": floor,
                "operation_label": self.operation_label,
            },
        )

    def post(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        service_method = getattr(
            FloorService,
            self.service_method,
        )

        try:
            updated_floor = service_method(
                actor=request.user,
                floor=floor,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        self.add_success_message(
            self.success_message
        )

        return redirect(
            "accommodation:floor-detail",
            pk=updated_floor.pk,
        )


class FloorActivateView(FloorStateChangeView):
    operation_label = "Activate Floor"
    success_message = "Floor activated successfully."

    policy_method = "can_activate_floor"
    service_method = "activate_floor"


class FloorDeactivateView(FloorStateChangeView):
    operation_label = "Deactivate Floor"
    success_message = "Floor deactivated successfully."

    policy_method = "can_deactivate_floor"
    service_method = "deactivate_floor"


class FloorMaintenanceView(FloorStateChangeView):
    operation_label = "Set Floor for Maintenance"
    success_message = "Floor set for maintenance."

    policy_method = "can_set_floor_maintenance"
    service_method = "set_maintenance"


# ============================================================
# FLOOR RESTRICTION OPERATIONS
# ============================================================

class FloorRestrictionOperationView(FloorOperationBaseView):
    """
    Base view for setting or removing floor restrictions.

    Restriction operations use their own authorization policies
    and service methods.

    The restriction note is handled by FloorRestrictionForm.
    """

    template_name = "accommodation/floor/floor_restriction_form.html"

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    form_class = FloorRestrictionForm

    def get_initial(self, floor):
        """
        Provide the current restriction note when displaying
        the restriction form.
        """
        return {
            "restriction_note": floor.restriction_note or "",
        }

    def get_form(self, floor):
        """
        Build the restriction form.

        Subclasses may override this when the operation does
        not require a form.
        """
        return self.form_class(
            initial=self.get_initial(floor)
        )

    def get_context_data(self, floor, form):
        """
        Provide operation-specific information to the template.
        """
        return {
            "floor": floor,
            "form": form,
            "operation_label": self.operation_label,
        }

    def get(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        form = self.get_form(floor)

        return render(
            request,
            self.template_name,
            self.get_context_data(floor, form),
        )

    def post(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        form = self.form_class(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context_data(floor, form),
            )

        service_method = getattr(
            FloorService,
            self.service_method,
        )

        try:
            updated_floor = self.execute_operation(
                service_method=service_method,
                actor=request.user,
                floor=floor,
                cleaned_data=form.cleaned_data,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        self.add_success_message(
            self.success_message
        )

        return redirect(
            "accommodation:floor-detail",
            pk=updated_floor.pk,
        )

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        """
        Execute the restriction service operation.

        Subclasses define the exact arguments passed to the service.
        """
        raise NotImplementedError(
            "Restriction operation must implement execute_operation()."
        )


class FloorSetRestrictionView(
    FloorRestrictionOperationView
):
    """
    Set a restriction on a floor.
    """

    operation_label = "Restrict Floor"
    success_message = "Floor restriction applied successfully."

    policy_method = "can_set_floor_restriction"
    service_method = "set_restriction"

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        return service_method(
            actor=actor,
            floor=floor,
            note=cleaned_data["restriction_note"],
        )


class FloorRemoveRestrictionView(
    FloorRestrictionOperationView
):
    """
    Remove an existing restriction from a floor.

    This operation does not require a restriction note.
    """

    template_name = "accommodation/floor/floor_confirm_operation.html"

    operation_label = "Remove Floor Restriction"
    success_message = "Floor restriction removed successfully."

    policy_method = "can_remove_floor_restriction"
    service_method = "remove_restriction"

    def get_form(self, floor):
        """
        Removing a restriction does not require user input.
        """
        return None

    def get_context_data(self, floor, form):
        return {
            "floor": floor,
            "operation_label": self.operation_label,
        }

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        return service_method(
            actor=actor,
            floor=floor,
        )


# ============================================================
# FLOOR BED CONFIGURATION OPERATIONS
# ============================================================

class FloorBedConfigurationOperationView(
    FloorOperationBaseView
):
    """
    Base view for setting or removing a floor-level
    bed-configuration override.

    The operation-specific policy and service method are
    retained in the concrete subclasses.
    """

    template_name = (
        "accommodation/floor/floor_bed_configuration_form.html"
    )

    operation_label = None
    success_message = None
    policy_method = None
    service_method = None

    form_class = FloorBedConfigurationForm

    def get_initial(self, floor):
        """
        Show the current override in the form.

        The building's default configuration is not treated
        as a floor override.
        """
        return {
            "bed_configuration": (
                floor.bed_configuration_override
            ),
        }

    def get_form(self, floor):
        return self.form_class(
            initial=self.get_initial(floor)
        )

    def get_context_data(self, floor, form):
        return {
            "floor": floor,
            "form": form,
            "operation_label": self.operation_label,
        }

    def get(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        form = self.get_form(floor)

        return render(
            request,
            self.template_name,
            self.get_context_data(floor, form),
        )

    def post(self, request, *args, **kwargs):
        floor = self.get_floor()

        if not self.check_operation_permission(
            request,
            floor,
            self.policy_method,
        ):
            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        form = self.form_class(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context_data(floor, form),
            )

        service_method = getattr(
            FloorService,
            self.service_method,
        )

        try:
            updated_floor = self.execute_operation(
                service_method=service_method,
                actor=request.user,
                floor=floor,
                cleaned_data=form.cleaned_data,
            )

        except DomainError as error:
            self.add_error_message(error.message)

            return redirect(
                "accommodation:floor-detail",
                pk=floor.pk,
            )

        self.add_success_message(
            self.success_message
        )

        return redirect(
            "accommodation:floor-detail",
            pk=updated_floor.pk,
        )

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        """
        Execute the configuration operation.

        Concrete subclasses define the service arguments.
        """
        raise NotImplementedError(
            "Bed configuration operation must implement execute_operation()."
        )


class FloorSetBedConfigurationView(
    FloorBedConfigurationOperationView
):
    """
    Set a floor-level bed-configuration override.
    """

    operation_label = "Change Floor Bed Configuration"
    success_message = (
        "Floor bed configuration updated successfully."
    )

    policy_method = "can_change_floor_bed_configuration"
    service_method = "set_bed_configuration_override"

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        return service_method(
            actor=actor,
            floor=floor,
            configuration=cleaned_data["bed_configuration"],
        )


class FloorRemoveBedConfigurationView(
    FloorBedConfigurationOperationView
):
    """
    Remove the floor-level bed-configuration override.

    The floor will inherit the building's default configuration.
    """

    template_name = (
        "accommodation/floor/floor_confirm_operation.html"
    )

    operation_label = "Remove Floor Bed Configuration Override"
    success_message = (
        "Floor bed configuration override removed successfully."
    )

    policy_method = "can_change_floor_bed_configuration"
    service_method = "remove_bed_configuration_override"

    def get_form(self, floor):
        """
        Removing an override does not require a configuration form.
        """
        return None

    def get_context_data(self, floor, form):
        return {
            "floor": floor,
            "operation_label": self.operation_label,
        }

    def execute_operation(
        self,
        service_method,
        actor,
        floor,
        cleaned_data,
    ):
        return service_method(
            actor=actor,
            floor=floor,
        )
