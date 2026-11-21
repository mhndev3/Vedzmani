from django.core.management.base import BaseCommand, CommandError

from apps.orders.torobpay import TorobPayClient, TorobPayError


class Command(BaseCommand):
    help = "Check TorobPay OAuth credentials without enabling or initiating payments."

    def handle(self, *args, **options):
        try:
            TorobPayClient().check_connection()
        except TorobPayError as exc:
            status = f" (HTTP {exc.http_status})" if exc.http_status else ""
            raise CommandError(
                f"TorobPay OAuth check failed: {exc.code}{status}"
            ) from None

        self.stdout.write(self.style.SUCCESS(
            "TorobPay OAuth authentication succeeded. Payment features remain disabled."
        ))
