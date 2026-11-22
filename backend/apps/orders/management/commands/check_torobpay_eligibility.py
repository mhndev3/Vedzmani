from django.core.management.base import BaseCommand, CommandError

from apps.orders.torobpay import TorobPayClient, TorobPayError


class Command(BaseCommand):
    help = "Run a read-only TorobPay eligibility check for an explicit amount in Rial."

    def add_arguments(self, parser):
        parser.add_argument(
            "--amount-rial",
            type=int,
            required=True,
            help="Amount to check, in Rial (not Toman).",
        )

    def handle(self, *args, **options):
        amount_rial = options["amount_rial"]
        try:
            result = TorobPayClient().check_eligibility(
                amount_rial,
                allow_when_disabled=True,
            )
        except TorobPayError as exc:
            status = f" (HTTP {exc.http_status})" if exc.http_status else ""
            raise CommandError(
                f"TorobPay eligibility check failed: {exc.code}{status}"
            ) from None

        eligible = "yes" if result["eligible"] else "no"
        self.stdout.write(self.style.SUCCESS(
            f"TorobPay eligibility check completed. Eligible: {eligible}. "
            "No payment was initiated."
        ))
