"""Single source of truth for phone normalization.

Vedzmani V1 targets Iranian mobile numbers. Every accepted spelling of the
same number normalizes to the same canonical form: ``+989XXXXXXXXX``.
Normalization is deterministic, pure (no I/O) and used by the User model,
the OTP services and the API serializers - never re-implement it elsewhere.
"""

import re

# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII digits.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_SEPARATORS = re.compile(r"[\s\-().\u200c\u200f\u200e]")
_NATIONAL = re.compile(r"9[0-9]{9}")

CANONICAL_RE = r"^\+989[0-9]{9}$"


class InvalidPhoneNumber(ValueError):
    """Raised when a value cannot be normalized to an Iranian mobile number."""


def normalize_phone(raw: object) -> str:
    """Return the canonical ``+989XXXXXXXXX`` form or raise InvalidPhoneNumber.

    Accepted: 09123456789, 9123456789, 989123456789, +989123456789,
    00989123456789 (with optional spaces/dashes and Persian/Arabic digits).
    The prefix is decided by total length, so a bare 10-digit national number
    that happens to start with "98" is not misread as a country code.
    """
    if not isinstance(raw, str):
        raise InvalidPhoneNumber("Phone number must be a string.")

    value = _SEPARATORS.sub("", raw.translate(_DIGITS))
    has_plus = value.startswith("+")
    if has_plus:
        value = value[1:]
    if not (value.isascii() and value.isdigit()):
        raise InvalidPhoneNumber("Phone number may only contain digits.")

    if has_plus:
        national = value[2:] if len(value) == 12 and value.startswith("98") else ""
    elif len(value) == 14 and value.startswith("0098"):
        national = value[4:]
    elif len(value) == 12 and value.startswith("98"):
        national = value[2:]
    elif len(value) == 11 and value.startswith("0"):
        national = value[1:]
    elif len(value) == 10:
        national = value
    else:
        national = ""

    if not _NATIONAL.fullmatch(national):
        raise InvalidPhoneNumber("Not a valid Iranian mobile number.")
    return f"+98{national}"
