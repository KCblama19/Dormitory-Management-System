
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accommodation.forms.campus_forms import CampusForm
from apps.accommodation.models.campus.campus_model import Campus
from apps.accommodation.services.campus_service import CampusService
from apps.accommodation.views.base import AccommodationBaseView

from apps.core.exceptions import DomainError, PermissionDenied
from apps.core.policies import AccommodationPolicy


class CampusUpdateView(AccommodationBaseView):
    """
    Update a campus's descriptive and location information.

    The university relationship is intentionally excluded from
    the editable fields and is never passed to the update service.
    """

    template_name = "accommodation/campus/campus_form.html"

    def get_campus(self):
        return get_object_or_404(
            Campus.objects.select_related("university"),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        campus = self.get_campus()

        if not AccommodationPolicy.can_update_campus(
            request.user,
            campus,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this campus."
                )
            )

        form = CampusForm(instance=campus)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "campus": campus,
                "page_title": "Update Campus",
                "submit_label": "Save Changes",
            },
        )

    def post(self, request, *args, **kwargs):
        campus = self.get_campus()

        if not AccommodationPolicy.can_update_campus(
            request.user,
            campus,
        ):
            return self.handle_domain_error(
                PermissionDenied(
                    "You do not have permission to update this campus."
                )
            )

        form = CampusForm(
            request.POST,
            instance=campus,
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "campus": campus,
                    "page_title": "Update Campus",
                    "submit_label": "Save Changes",
                },
            )

        data = form.cleaned_data

        try:
            updated_campus = CampusService.update_campus(
                actor=request.user,
                campus=campus,
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
            # Keep the submitted values so the user can correct
            # the problem without having to complete the form again.
            form.add_error(None, error.message)

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "campus": campus,
                    "page_title": "Update Campus",
                    "submit_label": "Save Changes",
                },
            )

        self.add_success_message(
            "Campus updated successfully."
        )

        return redirect(
            "accommodation:campus-detail",
            pk=updated_campus.pk,
        )
