"""OTP delivery boundary.

A tiny interface so a real SMS provider can be plugged in later by setting
``OTP_DELIVERY_BACKEND`` - no auth code changes. No real provider exists yet,
so the DEFAULT backend refuses to send (it never fakes success). Console and
in-memory backends are enabled only by dev/test settings; prod settings refuse
to boot with them.
"""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

NON_PRODUCTION_BACKENDS = {
    "apps.accounts.delivery.ConsoleDelivery",
    "apps.accounts.delivery.InMemoryDelivery",
}


class OTPDeliveryError(Exception):
    """Delivery failed or no provider is configured."""


class OTPDelivery:
    def send(self, *, phone: str, code: str, purpose: str) -> None:
        raise NotImplementedError


class UnconfiguredDelivery(OTPDelivery):
    """Production default until an SMS provider is integrated."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        raise OTPDeliveryError("No OTP delivery provider is configured.")


class ConsoleDelivery(OTPDelivery):
    """DEV ONLY: writes the code to the server log. Never used in production."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        logger.warning("DEV OTP delivery: phone=%s purpose=%s code=%s", phone, purpose, code)


class InMemoryDelivery(OTPDelivery):
    """TEST ONLY: captures messages so tests can read the code."""

    outbox: list[dict[str, str]] = []

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        type(self).outbox.append({"phone": phone, "code": code, "purpose": purpose})


def get_delivery() -> OTPDelivery:
    return import_string(settings.OTP_DELIVERY_BACKEND)()
