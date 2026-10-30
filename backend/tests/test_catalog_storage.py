from django.test import override_settings

from apps.catalog.storage import public_image_url


def test_product_image_uses_the_persistent_local_media_route_without_a_cdn():
    with override_settings(MEDIA_CDN_BASE_URL=""):
        assert public_image_url("products/hoodies/black/front.webp") == "/media/products/hoodies/black/front.webp"


def test_product_image_uses_the_configured_cdn_when_available():
    with override_settings(MEDIA_CDN_BASE_URL="https://images.example.test/catalog/"):
        assert public_image_url("products/hoodies/black/front.webp") == (
            "https://images.example.test/catalog/products/hoodies/black/front.webp"
        )
