"""Image storage boundary.

The database stores only the *storage key* (object path inside the
S3-compatible bucket). Public URLs are derived from the key plus a CDN base
URL, so nothing expiring (signed URLs) or secret ever becomes canonical data.

Uploading / WebP conversion is intentionally NOT implemented here: no
storage vendor or credentials exist yet (see PROJECT_CONTROL.md). A future
agent plugs an uploader in behind this module without touching the schema.
"""

from django.conf import settings

ALLOWED_IMAGE_CONTENT_TYPES = ("image/webp",)  # AVIF may be added later


def public_image_url(storage_key: str) -> str:
    """Return the CDN URL for a storage key (no credentials, no signing)."""
    base = (getattr(settings, "MEDIA_CDN_BASE_URL", "") or "").rstrip("/")
    return f"{base}/{storage_key}" if base else f"/{storage_key}"
