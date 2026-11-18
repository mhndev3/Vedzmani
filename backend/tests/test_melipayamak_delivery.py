"""Focused tests for the Melipayamak Console simple OTP adapter."""

import json

import pytest
from django.test import override_settings

from apps.accounts.delivery import MelipayamakDelivery, OTPDeliveryError


class _FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_sends_backend_generated_code_through_console_simple_api(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"recId": "1234567890123456", "status": ""})

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fake_urlopen)

    MelipayamakDelivery().send(phone="+989123456789", code="123456", purpose="login")

    assert captured["url"] == (
        "https://console.melipayamak.com/api/send/simple/test-console-token"
    )
    assert captured["timeout"] == 7
    assert captured["headers"]["Content-type"] == "application/json; charset=utf-8"
    assert captured["payload"] == {
        "from": "5000400004",
        "to": "09123456789",
        "text": "123456",
    }


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_provider_error_without_rec_id_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        "apps.accounts.delivery.urlopen",
        lambda *args, **kwargs: _FakeResponse({"recId": "", "status": "invalid sender"}),
    )
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")


@override_settings(
    MELIPAYAMAK_API_KEY="",
    MELIPAYAMAK_SENDER="",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_missing_credentials_fail_closed_without_network_call(monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("network must not be called without credentials")

    monkeypatch.setattr("apps.accounts.delivery.urlopen", unexpected_call)
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_invalid_code_and_phone_are_rejected_before_network(monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("network must not be called for invalid input")

    monkeypatch.setattr("apps.accounts.delivery.urlopen", unexpected_call)
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="12345", purpose="login")
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="123", code="123456", purpose="login")


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_network_failure_is_sanitized(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-token-and-phone-must-not-leak")

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with pytest.raises(OTPDeliveryError) as exc:
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")
    assert "secret-token" not in str(exc.value)
    assert "09123456789" not in str(exc.value)
