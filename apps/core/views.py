from django.contrib import messages
from django.shortcuts import redirect

from apps.core.exceptions import DomainError


def run_service_action(
    request,
    action,
    *,
    success_message,
    success_url,
):
    """Run a service operation and provide consistent user feedback."""
    try:
        action()
    except DomainError as exc:
        messages.error(request, str(exc))
        return None

    messages.success(request, success_message)
    return redirect(success_url)