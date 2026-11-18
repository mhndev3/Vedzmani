"""Focused tests for the Melipayamak shared-service OTP adapter."""

import json
from urllib.parse import parse_qs

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
    MELIPAYAMAK_USERNAME="09920000000",
    MELIPAYAMAK_API_KEY="test-api-key",
    MELIPAYAMAK_BASE_URL="https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber",
    MELIPAYAMAK_BODY_ID=591009,
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_sends_backend_generated_code_using_approved_shared_pattern(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        captured["form"] = parse_qs(request.data.decode("ascii"))
        return _FakeResponse({"Value": "1234567890123456", "RetStatus": 1, "StrRetStatus": "Ok"})

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fake_urlopen)

    MelipayamakDelivery().send(phone="+989123456789", code="123456", purpose="login")

    assert captured["url"] == "https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber"
    assert captured["timeout"] == 7
    assert captured["form"] == {
        "username": ["09920000000"],
        "password": ["test-api-key"],
        "text": ["123456"],
        "to": ["09123456789"],
        "bodyId": ["591009"],
    }


@override_settings(
    MELIPAYAMAK_USERNAME="09920000000",
    MELIPAYAMAK_API_KEY="test-api-key",
    MELIPAYAMAK_BASE_URL="https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber",
    MELIPAYAMAK_BODY_ID=591009,
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_provider_rejection_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        "apps.accounts.delivery.urlopen",
        lambda *args, **kwargs: _FakeResponse(
            {"Value": "35", "RetStatus": 35, "StrRetStatus": "InvalidData"}
        ),
    )
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")


@override_settings(
    MELIPAYAMAK_USERNAME="",
    MELIPAYAMAK_API_KEY="",
    MELIPAYAMAK_BASE_URL="https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber",
    MELIPAYAMAK_BODY_ID=591009,
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_missing_credentials_fail_closed_without_network_call(monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("network must not be called without credentials")

    monkeypatch.setattr("apps.accounts.delivery.urlopen", unexpected_call)
    with pytest.raises(OTPDeliveryError):
        MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")


@override_settings(
    MELIPAYAMAK_USERNAME="09920000000",
    MELIPAYAMAK_API_KEY="test-api-key",
    MELIPAYAMAK_BASE_URL="https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber",
    MELIPAYAMAK_BODY_ID=591009,
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
