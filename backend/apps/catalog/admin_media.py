"""Safe upload and ordering helpers for staff-managed catalog images."""
from __future__ import annotations

import os
import tempfile
import uuid
import warnings
from pathlib import Path

from django.conf import settings
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from .models import ColorVariant, VariantImage

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ACCEPTED_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _write_uploaded_webp(upload, variant: ColorVariant) -> tuple[str, int, int, int]:
    if not upload or upload.size <= 0:
        raise ValidationError({"file": "فایل تصویر خالی است."})
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({"file": "حجم هر تصویر نباید بیشتر از ۱۲ مگابایت باشد."})

    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in ACCEPTED_SOURCE_FORMATS:
                    raise ValidationError({"file": "فرمت تصویر باید JPEG، PNG یا WebP باشد."})
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValidationError({"file": "ابعاد تصویر بیش از حد مجاز است."})
                source.verify()
        upload.seek(0)
        with Image.open(upload) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            width, height = image.size
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise ValidationError({"file": "ابعاد تصویر معتبر نیست."})
            converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            key = f"products/{variant.product_id}/{variant.pk}/{uuid.uuid4().hex}.webp"
            root = Path(settings.MEDIA_ROOT).resolve()
            destination = root.joinpath(*key.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination_resolved = destination.resolve()
            destination_resolved.relative_to(root)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".tmp", prefix=".catalog-upload-", dir=destination.parent, delete=False
                ) as output:
                    temporary = output.name
                    converted.save(output, format="WEBP", quality=88, method=6)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(temporary, 0o644)
                os.replace(temporary, destination_resolved)
            finally:
                converted.close()
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            return key, width, height, destination_resolved.stat().st_size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError({"file": "فایل تصویر قابل خواندن یا پردازش نیست."}) from exc


def upload_variant_image(*, variant_id: int, upload, alt_text: str = "") -> VariantImage:
    with transaction.atomic():
        variant = ColorVariant.objects.select_for_update().get(pk=variant_id)
        active_images = list(VariantImage.objects.select_for_update().filter(variant=variant, is_active=True))
        key, width, height, file_size = _write_uploaded_webp(upload, variant)
        image = VariantImage.objects.create(
            variant=variant,
            storage_key=key,
            alt_text=alt_text[:200],
            position=max((item.position for item in active_images), default=-1) + 1,
            is_primary=not active_images,
            width=width,
            height=height,
            content_type="image/webp",
            file_size=file_size,
        )
        return image


@transaction.atomic
def reorder_variant_images(*, variant_id: int, image_ids: list[int]) -> list[VariantImage]:
    ColorVariant.objects.select_for_update().get(pk=variant_id)
    images = list(
        VariantImage.objects.select_for_update().filter(variant_id=variant_id, is_active=True).order_by("position", "id")
    )
    if len(image_ids) != len(images) or set(image_ids) != {image.pk for image in images}:
        raise ValidationError({"image_ids": "فهرست باید شامل تمام تصاویر فعال همین رنگ، بدون تکرار باشد."})

    by_id = {image.pk: image for image in images}
    ordered = [by_id[image_id] for image_id in image_ids]
    offset = max((image.position for image in images), default=0) + len(images) + 1
    for index, image in enumerate(ordered):
        image.position = offset + index
        image.is_primary = False
    VariantImage.objects.bulk_update(ordered, ["position", "is_primary"])
    for index, image in enumerate(ordered):
        image.position = index
        image.is_primary = index == 0
    VariantImage.objects.bulk_update(ordered, ["position", "is_primary"])
    return ordered


@transaction.atomic
def deactivate_variant_image(*, image_id: int) -> VariantImage:
    image = VariantImage.objects.select_for_update().select_related("variant").get(pk=image_id)
    ColorVariant.objects.select_for_update().get(pk=image.variant_id)
    was_primary = image.is_primary
    image.is_active = False
    image.is_primary = False
    image.save(update_fields=["is_active", "is_primary", "updated_at"])
    if was_primary:
        replacement = VariantImage.objects.select_for_update().filter(
            variant_id=image.variant_id, is_active=True
        ).order_by("position", "id").first()
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=["is_primary", "updated_at"])
    return image
