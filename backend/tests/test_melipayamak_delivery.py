"""Focused tests for the Melipayamak Console simple OTP adapter."""

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
def test_provider_rejection_logs_only_safe_status_metadata(monkeypatch, caplog):
    monkeypatch.setattr(
        "apps.accounts.delivery.urlopen",
        lambda *args, **kwargs: _FakeResponse(
            {"recId": "", "status": "private response containing phone 09123456789"}
        ),
    )
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")

    assert "non_numeric_or_missing" in caplog.text
    assert "09123456789" not in caplog.text
    assert "private response" not in caplog.text
    assert "test-console-token" not in caplog.text


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_http_error_logs_status_without_request_url_or_body(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise HTTPError(
            "https://console.melipayamak.com/api/send/simple/test-console-token",
            401,
            "unauthorized",
            hdrs=None,
            fp=BytesIO(b"private provider response"),
        )

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")

    assert "http_status=401" in caplog.text
    assert "test-console-token" not in caplog.text
    assert "09123456789" not in caplog.text
    assert "private provider response" not in caplog.text


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
def test_unexpected_network_failure_is_sanitized_and_classified(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-token-and-phone-must-not-leak")

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError) as exc:
            MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")

    assert "secret-token" not in str(exc.value)
    assert "09123456789" not in str(exc.value)
    assert "error_type=RuntimeError" in caplog.text
    assert "secret-token" not in caplog.text
    assert "09123456789" not in caplog.text
