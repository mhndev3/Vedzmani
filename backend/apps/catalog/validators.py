import re

from django.core.exceptions import ValidationError

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_hex_color(value: str) -> None:
    if not _HEX_RE.match(value or ""):
        raise ValidationError("Color must be a #RRGGBB hex value.")


def validate_storage_key(value: str) -> None:
    """Relative, normalised object key ending in .webp (WebP is required)."""
    if not value or value.startswith("/") or "\\" in value or ".." in value.split("/") or "//" in value:
        raise ValidationError("Storage key must be a clean relative object path.")
    if not value.lower().endswith(".webp"):
        raise ValidationError("Storage key must end with .webp.")
