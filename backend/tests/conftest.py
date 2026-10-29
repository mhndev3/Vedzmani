import json

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.delivery import InMemoryDelivery

# A valid checkout body (Iranian delivery details). The delivery phone is NOT part of it: it is the account phone.
DELIVERY = {
    "recipient_name": "Test Customer",
    "province": "Tehran",
    "city": "Tehran",
    "address": "No. 1, Example St.",
    "postal_code": "1234567890",
}


@pytest.fixture(autouse=True)
def _clean_state():
    """Rate-limit counters and the fake SMS outbox must not leak between tests."""
    cache.clear()
    InMemoryDelivery.outbox.clear()
    yield
    cache.clear()


class ApiClient:
    """Test client that behaves like a browser: CSRF checks ON, cookies kept."""

    def __init__(self):
        self.client = Client(enforce_csrf_checks=True)

    def _token(self):
        if "csrftoken" not in self.client.cookies:
            self.client.get("/api/auth/csrf/")
        return self.client.cookies["csrftoken"].value

    def get(self, path):
        return self.client.get(path)

    def post(self, path, data=None, *, csrf=True):
        extra = {"HTTP_X_CSRFTOKEN": self._token()} if csrf else {}
        return self.client.post(path, data=json.dumps(data or {}), content_type="application/json", **extra)

    # --- flow helpers -----------------------------------------------------
    def request_otp(self, phone="09123456789"):
        return self.post("/api/auth/otp/request/", {"phone": phone})

    def last_code(self):
        return InMemoryDelivery.outbox[-1]["code"]

    def verify(self, code, phone="09123456789", **extra):
        return self.post("/api/auth/otp/verify/", {"phone": phone, "code": code, **extra})

    def login(self, phone="09123456789", **extra):
        assert self.request_otp(phone).status_code == 202
        response = self.verify(self.last_code(), phone, **extra)
        assert response.status_code == 200, response.content
        return response


@pytest.fixture
def api():
    return ApiClient()


# --- admin test helpers -------------------------------------------------------
import itertools  # noqa: E402
from decimal import Decimal  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize  # noqa: E402

ADMIN_PASSWORD = "S3cret-pass-1"
_phone_counter = itertools.count(1)


def new_phone() -> str:
    return f"09{next(_phone_counter):09d}"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(new_phone(), password=ADMIN_PASSWORD)


@pytest.fixture
def su_client(superuser):
    return client_for(superuser)


@pytest.fixture
def customer_client(db):
    return client_for(get_user_model().objects.create_user(new_phone()))


@pytest.fixture
def make_staff(db):
    """Staff user holding exactly the given 'app_label.codename' permissions."""

    def _make(*perms):
        user = get_user_model().objects.create_user(new_phone(), is_staff=True)
        for perm in perms:
            app_label, codename = perm.split(".")
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return user

    return _make


@pytest.fixture
def make_variant_size(db):
    """Creates product + color + image + size row; returns the VariantSize."""

    def _make(stock=5):
        n = next(_phone_counter)
        category, _ = Category.objects.get_or_create(slug="admin-cat", defaults={"name": "Admin Cat"})
        product = Product.objects.create(
            category=category, name=f"Prod {n}", slug=f"prod-{n}", price=Decimal("1000"), is_active=True
        )
        variant = ColorVariant.objects.create(product=product, name="Black", slug="black", hex_color="#000000")
        size, _ = Size.objects.get_or_create(code="m", defaults={"label": "M"})
        VariantImage.objects.create(
            variant=variant, storage_key=f"prod-{n}/black/1.webp", position=0, is_primary=True, width=10, height=10
        )
        return VariantSize.objects.create(variant=variant, size=size, sku=f"SKU-{n}", stock_quantity=stock)

    return _make


# --- production static files for the prod-settings subprocess tests ------------------------------------------
# Under config.settings.prod, Django Admin pages render `{% static %}` through WhiteNoise's manifest storage, which
# raises "Missing staticfiles manifest entry" until `collectstatic` has produced backend/staticfiles/staticfiles.json.
# The production image does that at build time (backend/Dockerfile). A fresh checkout (CI, a new clone) has no such
# directory (it is git-ignored), so the tests below that serve /admin/ under prod settings need the same step; a
# developer machine that had ever run collectstatic hid the problem. This runs the same command with throwaway
# values, only when the manifest is missing, and only for modules that start a prod-settings subprocess.
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROD_SUBPROCESS_MODULES = {"test_production_proxy_behavior"}


@pytest.fixture(scope="module", autouse=True)
def _prod_static_manifest(request):
    if request.module.__name__.rsplit(".", 1)[-1] not in _PROD_SUBPROCESS_MODULES:
        return
    if (_BACKEND_DIR / "staticfiles" / "staticfiles.json").is_file():
        return
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "build-time-only-not-a-real-secret-key-0000000000",
        "DJANGO_ALLOWED_HOSTS": "build.invalid",
        "DATABASE_URL": "postgres://build:build@build.invalid:5432/build",
        "REDIS_URL": "redis://build.invalid:6379/0",
    }
    for name in ("OTP_DELIVERY_BACKEND", "DJANGO_SECURE_SSL_REDIRECT"):
        env.pop(name, None)
    result = subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput"],
        cwd=_BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"collectstatic failed:\n{result.stdout[-500:]}\n{result.stderr[-1500:]}"