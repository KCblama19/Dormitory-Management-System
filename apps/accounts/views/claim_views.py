from typing import Any

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from apps.accounts.models import User
from apps.accounts.forms.claim_forms import (
    VerifyUserCredentialsForm,
    VerifyUserDOBForm,
    UpdateUserPasswordForm,
)
from apps.accounts.services.claim_service import (
    verifyUserCredentials,
    verifyUserDOB,
    updateUserPassword,
)


class VerifyCredentialsView(FormView):

    template_name = "accounts/claim_account.html"
    form_class = VerifyUserCredentialsForm
    success_url = reverse_lazy("accounts:verify-dob")

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        context["step"] = "verify_credentials"
        context["title"] = "Verify your credentials"

        return context

    def form_valid(self, form):

        identifier = form.cleaned_data["identifier"]
        temp_password = form.cleaned_data["temp_password"]

        user = verifyUserCredentials(
            identifier=identifier,
            temp_password=temp_password,
        )

        if user is None:
            messages.error(
                self.request,
                "Invalid ID or password. Please try again.",
            )
            return self.form_invalid(form)

        self.request.session["claim_user_id"] = str(user.pk)

        return super().form_valid(form)


class VerifyUserDOBView(FormView):

    template_name = "accounts/claim_account.html"
    form_class = VerifyUserDOBForm
    success_url = reverse_lazy("accounts:update-password")

    def get_context_data(self, **kwargs) -> dict[str, Any]:

        context = super().get_context_data(**kwargs)

        context["step"] = "verify_date_of_birth"
        context["title"] = "Verify Your Date of Birth"

        return context

    def form_valid(self, form):

        user_id = self.request.session.get("claim_user_id")

        if not user_id:
            messages.error(
                self.request,
                "Session expired. Please restart verification.",
            )
            return redirect("accounts:verify-credentials")

        user = get_object_or_404(
            User,
            pk=user_id,
        )

        date_of_birth = form.cleaned_data["date_of_birth"]

        if verifyUserDOB(
            user=user,
            date_of_birth=date_of_birth,
        ):
            return super().form_valid(form)

        messages.error(
            self.request,
            "Date of birth is incorrect. Please try again.",
        )

        return self.form_invalid(form)


class UpdatePasswordView(FormView):

    template_name = "accounts/claim_account.html"
    form_class = UpdateUserPasswordForm
    success_url = reverse_lazy("accounts:login")

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["step"] = "update_password"
        context["title"] = "Update Password"

        return context

    def form_valid(self, form):

        user_id = self.request.session.get("claim_user_id")

        if not user_id:
            messages.error(
                self.request,
                "Session expired. Please restart verification.",
            )
            return redirect("accounts:verify-credentials")

        user = get_object_or_404(
            User,
            pk=user_id,
        )

        new_password = form.cleaned_data["new_password"]

        updated_user = updateUserPassword(
            user=user,
            new_password=new_password,
        )

        if updated_user is None:
            messages.error(
                self.request,
                "Unable to complete account claim. Please restart verification.",
            )
            return redirect("accounts:verify-credentials")

        self.request.session.pop("claim_user_id", None)

        messages.success(
            self.request,
            "Account claimed successfully. Please log in.",
        )

        return super().form_valid(form)