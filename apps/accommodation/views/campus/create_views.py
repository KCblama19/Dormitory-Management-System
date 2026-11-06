
from django.shortcuts import redirect, render

from apps.accommodation.forms.campus_forms import CampusForm
from apps.accommodation.services.campus_service import CampusService
from apps.core.policies import AccommodationPolicy

from apps.accommodation.views.base import AccommodationBaseView
from apps.core.exceptions import PermissionDenied, DomainError


class CampusCreateView(AccommodationBaseView):
    """
    Create a campus through CampusService.

    The form validates user input. The service owns the operation.
    """

    template_name = "accommodation/campus/campus_form.html"

    def get(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_campus(
            request.user,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create campuses."
                )
            )

        form = CampusForm()

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_title": "Create Campus",
                "submit_label": "Create Campus",
            },
        )

    def post(self, request, *args, **kwargs):
        if not AccommodationPolicy.can_create_campus(
            request.user,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to create campuses."
                )
            )

        form = CampusForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": "Create Campus",
                    "submit_label": "Create Campus",
                },
            )

        data = form.cleaned_data

        try:
            CampusService.create_campus(
                actor=request.user,
                university=data["university"],
                name=data["name"],
                code=data["code"],
                postal_code=data["postal_code"],
                address=data["address"],
                city=data["city"],
                province=data["province"],
                country=data["country"],
                description=data["description"],
            )

        except DomainError as error:
            return self.handle_domain_error(error)

        self.add_success_message(
            "Campus created successfully.",
        )

        return redirect("accommodation:campus-list")