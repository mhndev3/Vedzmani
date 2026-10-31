"""Responsive media generation keeps original WebP files intact and serves bounded renditions."""

from pathlib import Path

import pytest
from django.test import override_settings
from PIL import Image

from apps.catalog.image_processing import optimize_variant_image
from apps.catalog.models import Category, ColorVariant, Product, VariantImage

pytestmark = pytest.mark.django_db


def _variant_image(media_root: Path, *, key: str, size=(3200, 2400)) -> VariantImage:
    source = media_root / key
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 80, 160)).save(source, format="WEBP", quality=95)

    category = Category.objects.create(name="Hoodie", slug="hoodie-images")
    product = Product.objects.create(
        category=category, name="Hoodie", slug="hoodie-images", price=1000, is_active=True
    )
    variant = ColorVariant.objects.create(product=product, name="Black", slug="black")
    return VariantImage.objects.create(
        variant=variant,
        storage_key=key,
        position=0,
        is_primary=True,
        width=size[0],
        height=size[1],
    )


def test_responsive_renditions_are_generated_without_changing_original(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        image = _variant_image(tmp_path, key="products/hoodie.webp")
        original = tmp_path / image.storage_key
        assert optimize_variant_image(image.pk) is True

        image.refresh_from_db()
        thumbnail = tmp_path / image.thumbnail_storage_key
        display = tmp_path / image.display_storage_key

        assert image.thumbnail_storage_key.startswith("products/hoodie.") and image.thumbnail_storage_key.endswith(".w640.webp")
        assert image.display_storage_key.startswith("products/hoodie.") and image.display_storage_key.endswith(".w1600.webp")
        assert original.is_file()
        assert thumbnail.is_file()
        assert display.is_file()
        assert image.optimization_version == 1
        assert image.file_size == original.stat().st_size

        with Image.open(original) as source, Image.open(thumbnail) as small, Image.open(display) as medium:
            assert source.size == (3200, 2400)
            assert small.format == medium.format == "WEBP"
            assert max(small.size) <= 640
            assert max(medium.size) <= 1600

        assert optimize_variant_image(image.pk) is False


def test_small_images_use_original_without_creating_redundant_files(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        image = _variant_image(tmp_path, key="products/small.webp", size=(420, 560))
        assert optimize_variant_image(image.pk) is True

        image.refresh_from_db()
        assert image.thumbnail_storage_key == ""
        assert image.display_storage_key == ""
        assert image.optimization_version == 1
        assert list((tmp_path / "products").iterdir()) == [tmp_path / "products" / "small.webp"]


@pytest.mark.django_db(transaction=True)
def test_new_image_metadata_automatically_schedules_optimization(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        image = _variant_image(tmp_path, key="products/automatic.webp")
        image.refresh_from_db()

        assert image.optimization_version == 1
        assert image.thumbnail_storage_key.startswith("products/automatic.") and image.thumbnail_storage_key.endswith(".w640.webp")
        assert image.display_storage_key.startswith("products/automatic.") and image.display_storage_key.endswith(".w1600.webp")



def test_optimizer_dry_run_reports_missing_sources_without_writing(tmp_path):
    from io import StringIO

    from django.core.management import call_command
    from django.core.management.base import CommandError

    with override_settings(MEDIA_ROOT=tmp_path):
        image = _variant_image(tmp_path, key="products/not-copied-yet.webp")
        image.refresh_from_db()
        assert image.optimization_version == 0

        output = StringIO()
        with pytest.raises(CommandError, match="source file"):
            call_command("optimize_catalog_images", "--dry-run", stdout=output)

        assert "pending=1" in output.getvalue()
        assert "missing source files=1" in output.getvalue()
        image.refresh_from_db()
        assert image.optimization_version == 0
        assert image.thumbnail_storage_key == ""
        assert image.display_storage_key == ""
