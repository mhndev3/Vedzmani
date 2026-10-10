import json

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.delivery import InMemoryDelivery


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
