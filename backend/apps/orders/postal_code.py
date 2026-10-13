"""Iranian postal code normalization.

Pure (no I/O, no Django imports), like ``apps/accounts/phone.py``. An Iranian postal code is exactly 10 digits;
Persian (U+06F0..) and Arabic-Indic (U+0660..) digits are accepted and converted to ASCII. Surrounding
whitespace is ignored; anything else (separators, letters, other digit scripts, wrong length) is rejected.

Only the length/alphabet rule is enforced. Stricter national-postal-code rules (e.g. digit-position
restrictions) are NOT applied because no authoritative rule set has been provided by the product owner.
"""

POSTAL_CODE_LENGTH = 10

# Persian (U+06F0..U+06F9) and Arabic-Indic (U+0660..U+0669) digits -> ASCII digits.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class InvalidPostalCode(ValueError):
    """Raised when a value is not a valid 10-digit postal code."""


def normalize_postal_code(raw: object) -> str:
    """Return the canonical 10-digit ASCII postal code or raise ``InvalidPostalCode``.

    Non-strings are rejected on purpose: a JSON number would silently lose a leading zero.
    """
    if not isinstance(raw, str):
        raise InvalidPostalCode("Postal code must be a string.")
    value = raw.strip().translate(_DIGITS)
    if len(value) != POSTAL_CODE_LENGTH or not (value.isascii() and value.isdigit()):
        raise InvalidPostalCode("Postal code must be exactly 10 digits.")
    return value
