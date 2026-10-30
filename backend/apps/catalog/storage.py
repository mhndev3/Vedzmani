"""Image storage boundary.

The database stores only the *storage key* (object path inside the
S3-compatible bucket). Public URLs are derived from the key plus a CDN base
URL, so nothing expiring (signed URLs) or secret ever becomes canonical data.

Product binaries are kept outside PostgreSQL. In production, the backend writes
to MEDIA_ROOT and Nginx serves the same host-mounted directory read-only at
/media/. MEDIA_CDN_BASE_URL can override that local URL when a CDN is configured.
The storage key remains relative and must end in .webp.
"""

from django.conf import settings

ALLOWED_IMAGE_CONTENT_TYPES = ("image/webp",)  # AVIF may be added later


def public_image_url(storage_key: str) -> str:
    """Return the CDN URL for a storage key (no credentials, no signing)."""
    base = (getattr(settings, "MEDIA_CDN_BASE_URL", "") or "").rstrip("/")
    key = storage_key.lstrip("/")
    return f"{base}/{key}" if base else f"/media/{key}"
