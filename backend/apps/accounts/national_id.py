"""Validation and privacy-preserving fingerprinting for Iranian national IDs."""

import hashlib
import hmac
import re

from django.conf import settings

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class InvalidNationalId(ValueError):
    """Raised when an Iranian national ID fails format or checksum validation."""


def normalize_national_id(raw: object) -> str:
    if not isinstance(raw, str):
        raise InvalidNationalId("National ID must be a string.")
    value = raw.translate(_DIGITS).strip().replace(" ", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{10}", value) or len(set(value)) == 1:
        raise InvalidNationalId("Enter a valid 10-digit national ID.")
    checksum = sum(int(value[index]) * (10 - index) for index in range(9)) % 11
    expected = checksum if checksum < 2 else 11 - checksum
    if expected != int(value[-1]):
        raise InvalidNationalId("National ID checksum is invalid.")
    return value


def national_id_digest(value: str) -> str:
    """HMAC prevents storing the government identifier in readable form.

    Keep Django SECRET_KEY stable: it is the keyed fingerprint salt used for uniqueness.
    """
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, b"vedzmani:national-id:" + value.encode("ascii"), hashlib.sha256).hexdigest()
