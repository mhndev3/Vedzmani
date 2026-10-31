"""Generate immutable, bounded WebP renditions for catalog media.

The original object is never modified. Derived files get new storage keys so
Nginx/CDN's long-lived immutable cache remains correct and rollback is trivial.
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import VariantImage

logger = logging.getLogger(__name__)

THUMBNAIL_MAX_EDGE = 640
DISPLAY_MAX_EDGE = 1600
WEBP_QUALITY = 80
OPTIMIZATION_VERSION = 1


def _media_path(storage_key: str) -> Path:
    """Resolve a relative storage key and reject paths or symlinks outside MEDIA_ROOT."""
    key = PurePosixPath(storage_key)
    if key.is_absolute() or not key.parts or any(part in {"", ".", ".."} for part in key.parts):
        raise ValueError("Image storage key must be a clean relative path.")

    root = Path(settings.MEDIA_ROOT).resolve()
    target = root.joinpath(*key.parts).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Image storage key escapes MEDIA_ROOT.") from exc
    return target


def _source_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _write_webp_variant(image: Image.Image, output_path: Path) -> None:
    """Write atomically so Nginx never observes a partially written image."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    converted = image.convert("RGBA" if has_alpha else "RGB")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".tmp", prefix=".vedzmani-image-", dir=output_path.parent, delete=False
        ) as temp_file:
            temp_name = temp_file.name
            converted.save(temp_file, format="WEBP", quality=WEBP_QUALITY, method=6)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        # Nginx runs under a separate, unprivileged UID in production; derivatives
        # must be readable by the shared read-only media mount.
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, output_path)
    finally:
        converted.close()
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def optimize_variant_image(image_id: int, *, force: bool = False) -> bool:
    """Create 640px and 1600px renditions for one VariantImage.

    Returns True when a row was processed. Missing source files return False so
    metadata can be created before the media copy; the management command can
    safely backfill those rows after files arrive.
    """
    image = VariantImage.objects.get(pk=image_id)
    if image.optimization_version >= OPTIMIZATION_VERSION and not force:
        return False

    source_path = _media_path(image.storage_key)
    if not source_path.is_file():
        logger.warning("Catalog image source is not present yet: %s", image.storage_key)
        return False

    try:
        with Image.open(source_path) as source:
            if source.format != "WEBP":
                raise ValueError(f"Expected a WebP source image: {image.storage_key}")
            oriented = ImageOps.exif_transpose(source)
            oriented.load()
            original_width, original_height = oriented.size
            if original_width < 1 or original_height < 1:
                raise ValueError(f"Image has invalid dimensions: {image.storage_key}")

            generated_keys: dict[int, str] = {}
            fingerprint = _source_fingerprint(source_path)
            for max_edge in (THUMBNAIL_MAX_EDGE, DISPLAY_MAX_EDGE):
                if max(original_width, original_height) <= max_edge:
                    generated_keys[max_edge] = ""
                    continue

                source_key = PurePosixPath(image.storage_key)
                suffix = f".{fingerprint}.w{max_edge}.webp"
                parent = "" if str(source_key.parent) == "." else source_key.parent.as_posix() + "/"
                available_stem = 500 - len(parent) - len(suffix)
                if available_stem < 1:
                    raise ValueError(f"Image storage path is too long for renditions: {image.storage_key}")
                output_key = parent + source_key.stem[:available_stem] + suffix
                output_path = _media_path(output_key)
                rendition = oriented.copy()
                try:
                    rendition.thumbnail(
                        (max_edge, max_edge),
                        resample=Image.Resampling.LANCZOS,
                        reducing_gap=3.0,
                    )
                    _write_webp_variant(rendition, output_path)
                finally:
                    rendition.close()
                generated_keys[max_edge] = output_key

        VariantImage.objects.filter(pk=image.pk).update(
            thumbnail_storage_key=generated_keys[THUMBNAIL_MAX_EDGE],
            display_storage_key=generated_keys[DISPLAY_MAX_EDGE],
            optimization_version=OPTIMIZATION_VERSION,
            width=original_width,
            height=original_height,
            file_size=source_path.stat().st_size,
        )
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        logger.exception("Could not optimize catalog image %s", image.storage_key)
        raise


def schedule_variant_image_optimization(image: VariantImage) -> None:
    """Run after the metadata transaction commits; absent files remain backfillable."""
    if image.optimization_version >= OPTIMIZATION_VERSION:
        return

    image_id = image.pk

    def process() -> None:
        try:
            optimize_variant_image(image_id)
        except Exception:
            # A failed image should not roll back product metadata. It remains at
            # optimization_version=0 and is visible to optimize_catalog_images.
            logger.exception("Automatic catalog image optimization failed for image id=%s", image_id)

    transaction.on_commit(process, robust=True)
