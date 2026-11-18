"""OTP delivery boundary and provider adapters.

Real providers are isolated here so OTP generation, hashing, expiry and verification
remain owned by the Vedzmani backend.
"""

import json
import logging
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    """Production default until an SMS provider is configured."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        raise OTPDeliveryError("No OTP delivery provider is configured.")


class MelipayamakDelivery(OTPDelivery):
    """Send a backend-generated OTP through Melipayamak's shared service pattern."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        username = settings.MELIPAYAMAK_USERNAME
        api_key = settings.MELIPAYAMAK_API_KEY
        endpoint = settings.MELIPAYAMAK_BASE_URL
        body_id = settings.MELIPAYAMAK_BODY_ID
        timeout = settings.MELIPAYAMAK_TIMEOUT_SECONDS

        if not username or not api_key:
            raise OTPDeliveryError("Melipayamak credentials are not configured.")
        if not endpoint.startswith("https://"):
            raise OTPDeliveryError("Melipayamak endpoint must use HTTPS.")
        if not re.fullmatch(r"\d{6}", code):
            raise OTPDeliveryError("OTP code must contain exactly six digits.")

        recipient = self._normalize_iranian_mobile(phone)
        payload = urlencode(
            {
                "username": username,
                # Melipayamak's REST API expects the API key in the password field.
                "password": api_key,
                "text": code,
                "to": recipient,
                "bodyId": str(body_id),
            }
        ).encode("ascii")
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - provider/network details may contain credentials or phone numbers
            raise OTPDeliveryError("Melipayamak request failed.") from None

        if not isinstance(result, dict):
            raise OTPDeliveryError("Melipayamak returned an invalid response.")

        try:
            accepted = (
                int(result.get("RetStatus")) == 1
                and str(result.get("StrRetStatus", "")).strip().lower() == "ok"
                and bool(str(result.get("Value", "")).strip())
            )
        except (TypeError, ValueError):
            accepted = False

        if not accepted:
            # Never include provider response text: it is not trusted and may contain sensitive data.
            raise OTPDeliveryError("Melipayamak rejected the OTP message.")

    @staticmethod
    def _normalize_iranian_mobile(phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("0098"):
            digits = "0" + digits[4:]
        elif digits.startswith("98") and len(digits) == 12:
            digits = "0" + digits[2:]
        elif digits.startswith("9") and len(digits) == 10:
            digits = "0" + digits
        if not re.fullmatch(r"09\d{9}", digits):
            raise OTPDeliveryError("Recipient must be an Iranian mobile number.")
        return digits


class ConsoleDelivery(OTPDelivery):
    """DEV ONLY: writes the code to the server log. Never use in production."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        logger.warning("DEV OTP delivery: phone=%s purpose=%s code=%s", phone, purpose, code)


class InMemoryDelivery(OTPDelivery):
    """TEST ONLY: captures messages so tests can read the code."""

    outbox: list[dict[str, str]] = []

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        type(self).outbox.append({"phone": phone, "code": code, "purpose": purpose})


def get_delivery() -> OTPDelivery:
    return import_string(settings.OTP_DELIVERY_BACKEND)()
