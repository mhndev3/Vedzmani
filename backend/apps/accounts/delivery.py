"""OTP delivery boundary and provider adapters.

Real providers are isolated here so OTP generation, hashing, expiry and verification
remain owned by the Vedzmani backend.
"""

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
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
    """Send a backend-generated OTP through Melipayamak Console simple API."""

    API_URL = "https://console.melipayamak.com/api/send/simple/"

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        api_key = settings.MELIPAYAMAK_API_KEY
        sender = settings.MELIPAYAMAK_SENDER
        timeout = settings.MELIPAYAMAK_TIMEOUT_SECONDS

        if not api_key or not sender:
            raise OTPDeliveryError("Melipayamak credentials or sender are not configured.")
        if not re.fullmatch(r"\d{6}", code):
            raise OTPDeliveryError("OTP code must contain exactly six digits.")

        recipient = self._normalize_iranian_mobile(phone)
        payload = json.dumps(
            {"from": sender, "to": recipient, "text": code},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self.API_URL}{quote(api_key, safe='')}",
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                http_status = getattr(response, "status", None)
                try:
                    result = json.loads(response.read().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning(
                        "Melipayamak response invalid JSON (http_status=%s)",
                        http_status,
                    )
                    raise OTPDeliveryError("Melipayamak returned an invalid response.") from None
        except HTTPError as exc:
            logger.warning("Melipayamak HTTP error (http_status=%s)", exc.code)
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except URLError as exc:
            # Log only the reason class; the reason text can contain sensitive URL data.
            logger.warning(
                "Melipayamak network error (reason_type=%s)",
                type(exc.reason).__name__,
            )
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except (TimeoutError, OSError) as exc:
            logger.warning("Melipayamak transport error (error_type=%s)", type(exc).__name__)
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except OTPDeliveryError:
            raise
        except Exception as exc:  # noqa: BLE001 - never log provider exception text or request URL
            logger.warning("Melipayamak unexpected error (error_type=%s)", type(exc).__name__)
            raise OTPDeliveryError("Melipayamak request failed.") from None

        if not isinstance(result, dict) or not str(result.get("recId", "")).strip():
            status = result.get("status") if isinstance(result, dict) else None
            # Only expose numeric provider status codes; arbitrary text may contain PII/secrets.
            safe_status = status if isinstance(status, int) or (
                isinstance(status, str) and status.isdigit() and len(status) <= 6
            ) else "non_numeric_or_missing"
            logger.warning(
                "Melipayamak rejected message (http_status=%s provider_status=%s response_type=%s)",
                http_status,
                safe_status,
                type(result).__name__,
            )
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
