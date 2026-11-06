
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    DomainError,
    PermissionDenied,
    ValidationError,
    ConflictError,
    NotFoundError,
)


class AccommodationBaseView(LoginRequiredMixin, View):
    """
    Shared base for accommodation management views.

    Authentication is handled here, while object-level authorization
    remains explicit in each view through AccommodationPolicy.

    Mutations must be delegated to the corresponding service. This
    class only handles the HTTP boundary and application exceptions.
    """

    login_url = "login"

    def handle_domain_error(self, error):
        """
        Convert an application exception into user-facing feedback.

        Domain exceptions should not escape into Django's default
        error pages during ordinary management operations.
        """
        if isinstance(error, PermissionDenied):
            messages.error(self.request, error.message)
            return redirect(self.get_fallback_url())

        if isinstance(error, NotFoundError):
            messages.error(self.request, error.message)
            return redirect(self.get_fallback_url())

        if isinstance(error, ConflictError):
            messages.warning(self.request, error.message)
            return redirect(self.get_fallback_url())

        if isinstance(error, ValidationError):
            messages.error(self.request, error.message)
            return redirect(self.get_fallback_url())

        messages.error(
            self.request,
            "The requested operation could not be completed.",
        )
        return redirect(self.get_fallback_url())

    def get_fallback_url(self):
        """
        Override in subclasses when a more specific fallback is available.
        """
        return "accommodation:campus-list"

    def add_success_message(self, message):
        messages.success(self.request, message)

    def add_error_message(self, message):
        messages.error(self.request, message)


class BuildingBaseView(AccommodationBaseView):
    def get_fallback_url(self):
        return "accommodation:building-list"