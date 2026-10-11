"""Iranian postal code normalizer (pure function, no database)."""

import pytest

from apps.orders.postal_code import InvalidPostalCode, normalize_postal_code


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234567890", "1234567890"),
        ("۱۲۳۴۵۶۷۸۹۰", "1234567890"),  # Persian digits
        ("١٢٣٤٥٦٧٨٩٠", "1234567890"),  # Arabic-Indic digits
        ("12۳۴567890", "1234567890"),  # mixed scripts
        ("  1234567890  ", "1234567890"),  # surrounding whitespace is ignored
        ("0123456789", "0123456789"),  # a leading zero is kept (hence strings only)
        ("۰123456789", "0123456789"),
    ],
)
def test_valid_postal_codes_are_normalized_to_ascii(raw, expected):
    assert normalize_postal_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "123456789",  # 9 digits
        "12345678901",  # 11 digits
        "12345-67890",  # separators are not accepted
        "1234 567890",
        "12345abcde",
        "１２３４５６７８９０",  # full-width digits are not a supported script
        "12345678９0",
        "1234567890\n1",
        None,
        1234567890,  # a JSON number would lose a leading zero, so non-strings are rejected
        True,
        ["1234567890"],
    ],
)
def test_invalid_postal_codes_are_rejected(raw):
    with pytest.raises(InvalidPostalCode):
        normalize_postal_code(raw)
