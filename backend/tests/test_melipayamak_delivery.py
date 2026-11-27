"""Focused tests for the Melipayamak shared-service OTP adapter."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from django.test import override_settings

from apps.accounts.delivery import MelipayamakDelivery, OTPDeliveryError


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


@pytest.fixture
def melipayamak_settings():
    with override_settings(
        MELIPAYAMAK_SHARED_API_URL="https://console.melipayamak.com/api/send/shared/test-secret",
        MELIPAYAMAK_BODY_ID=591009,
        MELIPAYAMAK_TIMEOUT_SECONDS=7,
    ):
        yield


def test_sends_backend_generated_code_through_shared_api(monkeypatch, melipayamak_settings):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"recId": 3741437414, "status": ""})

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fake_urlopen)

    MelipayamakDelivery().send(phone="+989123456789", code="123456", purpose="login")

    assert captured["url"].endswith("/test-secret")
    assert captured["timeout"] == 7
    assert captured["headers"]["Content-type"] == "application/json; charset=utf-8"
    assert captured["payload"] == {
        "bodyId": 591009,
        "to": "09123456789",
        "args": ["123456"],
    }


@pytest.mark.parametrize("purpose", ["login", "signup", "password_reset"])
def test_all_otp_purposes_use_the_approved_template_variable(
    monkeypatch, melipayamak_settings, purpose
):
    payloads = []

    def fake_urlopen(request, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse({"recId": 3741437414, "status": ""})

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fake_urlopen)
    MelipayamakDelivery().send(phone="09123456789", code="654321", purpose=purpose)

    assert payloads == [{"bodyId": 591009, "to": "09123456789", "args": ["654321"]}]


def test_rejects_provider_error_without_leaking_response_or_endpoint(
    monkeypatch, melipayamak_settings, caplog
):
    monkeypatch.setattr(
        "apps.accounts.delivery.urlopen",
        lambda *args, **kwargs: _FakeResponse(
            {"recId": None, "status": "private error for 09123456789"}
        ),
    )
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(
                phone="09123456789", code="123456", purpose="signup"
            )

    assert "09123456789" not in caplog.text
    assert "private error" not in caplog.text
    assert "test-secret" not in caplog.text


def test_http_error_does_not_log_endpoint_or_response_body(
    monkeypatch, melipayamak_settings, caplog
):
    def fail(*args, **kwargs):
        raise HTTPError(
            "https://console.melipayamak.com/api/send/shared/test-secret",
            401,
            "unauthorized",
            hdrs=None,
            fp=BytesIO(b"private provider response"),
        )

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(
                phone="09123456789", code="123456", purpose="signup"
            )

    assert "http_status=401" in caplog.text
    assert "test-secret" not in caplog.text
    assert "private provider response" not in caplog.text


def test_missing_configuration_fails_closed(monkeypatch):
    with override_settings(
        MELIPAYAMAK_SHARED_API_URL="",
        MELIPAYAMAK_BODY_ID=591009,
        MELIPAYAMAK_TIMEOUT_SECONDS=7,
    ):
        monkeypatch.setattr(
            "apps.accounts.delivery.urlopen",
            lambda *args, **kwargs: pytest.fail("network must not be called"),
        )
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(
                phone="09123456789", code="123456", purpose="signup"
            )


def test_invalid_code_phone_and_purpose_are_rejected_before_network(
    monkeypatch, melipayamak_settings
):
    monkeypatch.setattr(
        "apps.accounts.delivery.urlopen",
        lambda *args, **kwargs: pytest.fail("network must not be called"),
    )
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="12345", purpose="login")
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="123", code="123456", purpose="login")
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="other")
