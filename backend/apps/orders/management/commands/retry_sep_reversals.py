"""Retry SEP reversals that were not confirmed during the customer callback.

Run without --execute first to inspect the eligible backlog. The command only
marks an attempt reversed after an explicit successful SEP response.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.orders.models import SepPaymentAttempt
from apps.orders.sep import SepClient, SepError


class Command(BaseCommand):
    help = "Retry unconfirmed SEP reversals; dry-run unless --execute is supplied."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Send ReverseTransaction requests.")
        parser.add_argument("--min-age-minutes", type=int, default=5, help="Only retry attempts at least this old.")
        parser.add_argument("--limit", type=int, default=100, help="Maximum attempts to inspect per run.")

    def handle(self, *args, **options):
        min_age = options["min_age_minutes"]
        limit = options["limit"]
        if min_age < 0 or limit < 1:
            raise CommandError("--min-age-minutes must be >= 0 and --limit must be >= 1.")

        cutoff = timezone.now() - timedelta(minutes=min_age)
        eligible = SepPaymentAttempt.objects.filter(
            status__in=[SepPaymentAttempt.OUT_OF_STOCK, SepPaymentAttempt.REVERSAL_PENDING],
            ref_num__isnull=False,
            created_at__lte=cutoff,
        ).exclude(ref_num="").order_by("created_at", "pk")
        attempt_ids = list(eligible.values_list("pk", flat=True)[:limit])
        mode = "EXECUTE" if options["execute"] else "DRY RUN"
        self.stdout.write(f"[{mode}] retry_sep_reversals: {len(attempt_ids)} eligible attempt(s)")

        if not options["execute"]:
            self.stdout.write("No provider requests sent. Re-run with --execute to retry reversals.")
            return

        confirmed = 0
        pending = 0
        for attempt_id in attempt_ids:
            try:
                # Keep concurrent command invocations from processing the same row at once.
                # SEP reversal is also expected to be idempotent for a repeated RefNum.
                with transaction.atomic():
                    attempt = SepPaymentAttempt.objects.select_for_update().get(pk=attempt_id)
                    if attempt.status not in {
                        SepPaymentAttempt.OUT_OF_STOCK,
                        SepPaymentAttempt.REVERSAL_PENDING,
                    } or not attempt.ref_num:
                        continue
                    response = SepClient().reverse(attempt.ref_num)
                    if response.get("Success") is True and response.get("ResultCode") == 0:
                        attempt.status = SepPaymentAttempt.REVERSED
                        attempt.save(update_fields=["status", "updated_at"])
                        confirmed += 1
                    else:
                        pending += 1
            except SepError:
                pending += 1

        self.stdout.write(
            f"reversal confirmed: {confirmed}; still pending: {pending}. "
            "Unconfirmed attempts remain eligible for a later run."
        )
