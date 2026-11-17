from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.assignments.models import Assignment
from apps.assignments.services.assignment_service import AssignmentService
from apps.assignments.services.transfer_service import TransferService
from apps.core.exceptions import NotFoundError


class Command(BaseCommand):
    help = "Mark overdue accommodation reservations and expire them after grace."

    def handle(self, *args, **options):
        # A campus can already be on the next calendar day. Include that
        # date here and let each service apply the exact local cutoff.
        latest_candidate_date = timezone.now().date() + timedelta(days=1)

        candidates = (
            Assignment.objects.filter(
                status=Assignment.Status.RESERVED,
                check_in_deadline__lte=latest_candidate_date,
            )
            .order_by("pk")
            .values_list("pk", "transfer_request_id")
        )

        overdue_count = 0
        expired_count = 0

        for assignment_id, transfer_id in candidates.iterator(chunk_size=500):
            try:
                if transfer_id is None:
                    result = AssignmentService.process_reservation_deadline(
                        assignment_id=assignment_id,
                    )
                else:
                    result = TransferService.process_transfer_deadline(
                        transfer_id=transfer_id,
                    )
            except NotFoundError:
                self.stderr.write(
                    f"Assignment {assignment_id} or its transfer "
                    "could not be found. Skipping."
                )
                continue

            if result == "overdue":
                overdue_count += 1
            elif result == "expired":
                expired_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Marked overdue: {overdue_count}. Expired: {expired_count}."
            )
        )