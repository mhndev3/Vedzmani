"""OTP delivery boundary and provider adapters.

Real providers are isolated here so OTP generation, hashing, expiry and verification
remain owned by the Vedzmani backend.
"""

import json
import logging
import re
from urllib.error import HTTPError, URLError
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
    """Send backend-generated OTPs through Melipayamak's shared service API."""

    def send(self, *, phone: str, code: str, purpose: str) -> None:
        endpoint = settings.MELIPAYAMAK_SHARED_API_URL
        body_id = settings.MELIPAYAMAK_BODY_ID
        timeout = settings.MELIPAYAMAK_TIMEOUT_SECONDS

        if not endpoint:
            raise OTPDeliveryError("Melipayamak shared API is not configured.")
        if not re.fullmatch(r"\\d{6}", code):
            raise OTPDeliveryError("OTP code must contain exactly six digits.")
        if purpose not in {"login", "signup", "password_reset"}:
            raise OTPDeliveryError("Unsupported OTP purpose.")

        recipient = self._normalize_iranian_mobile(phone)
        payload = json.dumps(
            {"bodyId": body_id, "to": recipient, "args": [code]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            endpoint,
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
                        "Melipayamak shared API returned invalid JSON (http_status=%s)",
                        http_status,
                    )
                    raise OTPDeliveryError("Melipayamak returned an invalid response.") from None
        except HTTPError as exc:
            logger.warning("Melipayamak shared API HTTP error (http_status=%s)", exc.code)
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except URLError as exc:
            logger.warning(
                "Melipayamak shared API network error (reason_type=%s)",
                type(exc.reason).__name__,
            )
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except (TimeoutError, OSError) as exc:
            logger.warning(
                "Melipayamak shared API transport error (error_type=%s)",
                type(exc).__name__,
            )
            raise OTPDeliveryError("Melipayamak request failed.") from None
        except OTPDeliveryError:
            raise
        except Exception as exc:  # noqa: BLE001 - never log provider URL or response text
            logger.warning(
                "Melipayamak shared API unexpected error (error_type=%s)",
                type(exc).__name__,
            )
            raise OTPDeliveryError("Melipayamak request failed.") from None

        rec_id = result.get("recId") if isinstance(result, dict) else None
        valid_rec_id = (
            isinstance(rec_id, int) and not isinstance(rec_id, bool) and rec_id > 0
        ) or (
            isinstance(rec_id, str) and rec_id.isdigit() and len(rec_id) <= 24
        )
        if not valid_rec_id:
            logger.warning(
                "Melipayamak shared API rejected message (http_status=%s response_type=%s)",
                http_status,
                type(result).__name__,
            )
            raise OTPDeliveryError("Melipayamak rejected the OTP message.")

    @staticmethod
    def _normalize_iranian_mobile(phone: str) -> str:
        digits = re.sub(r"\\D", "", phone)
        if digits.startswith("0098"):
            digits = "0" + digits[4:]
        elif digits.startswith("98") and len(digits) == 12:
            digits = "0" + digits[2:]
        elif digits.startswith("9") and len(digits) == 10:
            digits = "0" + digits
        if not re.fullmatch(r"09\\d{9}", digits):
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
