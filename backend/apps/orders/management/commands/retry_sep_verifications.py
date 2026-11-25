"""Retry SEP Verify calls for callbacks that timed out before a decision.

Run without --execute to inspect eligible attempts. Executing this command
re-enters the normal callback service, which only fulfills an order after a
complete server-side SEP verification and stock check.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.orders.models import SepPaymentAttempt
from apps.orders.payment_services import process_sep_callback


class Command(BaseCommand):
    help = "Retry SEP verification for callback attempts left pending after a timeout."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Contact SEP and reconcile pending attempts.")
        parser.add_argument("--min-age-minutes", type=int, default=5, help="Only retry attempts at least this old.")
        parser.add_argument("--limit", type=int, default=100, help="Maximum attempts to inspect per run.")

    def handle(self, *args, **options):
        min_age = options["min_age_minutes"]
        limit = options["limit"]
        if min_age < 0 or limit < 1:
            raise CommandError("--min-age-minutes must be >= 0 and --limit must be >= 1.")

        cutoff = timezone.now() - timedelta(minutes=min_age)
        eligible = SepPaymentAttempt.objects.filter(
            status=SepPaymentAttempt.PENDING,
            ref_num__isnull=False,
            created_at__lte=cutoff,
        ).exclude(ref_num="").order_by("created_at", "pk")
        attempts = list(eligible.values_list("res_num", "ref_num")[:limit])
        mode = "EXECUTE" if options["execute"] else "DRY RUN"
        self.stdout.write(f"[{mode}] retry_sep_verifications: {len(attempts)} eligible attempt(s)")

        if not options["execute"]:
            self.stdout.write("No provider requests sent. Re-run with --execute to retry verification.")
            return

        paid = 0
        out_of_stock = 0
        failed = 0
        pending = 0
        for res_num, ref_num in attempts:
            result = process_sep_callback(res_num=res_num, ref_num=ref_num)
            if result == "paid":
                paid += 1
            elif result == "out_of_stock":
                out_of_stock += 1
            elif result == "pending":
                pending += 1
            else:
                failed += 1

        self.stdout.write(
            f"paid: {paid}; out_of_stock/reversed: {out_of_stock}; "
            f"failed: {failed}; still pending: {pending}."
        )
