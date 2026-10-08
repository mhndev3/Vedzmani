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
