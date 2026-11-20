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
        "text": "کاربر گرامی، کد ورود شما: 123456\nاین کد را در اختیار هیچ‌کس قرار ندهید.\nVedzmani",
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
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_http_error_classifies_provider_body_without_logging_contents(monkeypatch, caplog):
    private_detail = "Invalid sender for phone 09123456789 and code 123456"

    def fail(*args, **kwargs):
        raise HTTPError(
            "https://console.melipayamak.com/api/send/simple/test-console-token",
            400,
            "bad request",
            hdrs=None,
            fp=BytesIO(json.dumps({"status": private_detail}).encode("utf-8")),
        )

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")

    assert "http_status=400" in caplog.text
    assert "provider_error_category=sender" in caplog.text
    assert "09123456789" not in caplog.text
    assert "123456" not in caplog.text
    assert "Invalid sender" not in caplog.text
    assert "test-console-token" not in caplog.text



@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_nested_http_error_is_classified_and_numeric_code_is_safe(monkeypatch, caplog):
    private_detail = "Invalid sender for phone 09123456789 and code 123456"

    def fail(*args, **kwargs):
        body = {"errors": [{"field": "from", "message": private_detail}], "meta": {"error_code": "2401"}}
        raise HTTPError(
            "https://console.melipayamak.com/api/send/simple/test-console-token",
            400,
            "bad request",
            hdrs=None,
            fp=BytesIO(json.dumps(body).encode("utf-8")),
        )

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(phone="09123456789", code="123456", purpose="login")

    assert "provider_error_category=sender" in caplog.text
    assert "provider_error_code=2401" in caplog.text
    assert "09123456789" not in caplog.text
    assert "123456" not in caplog.text
    assert "Invalid sender" not in caplog.text
    assert "test-console-token" not in caplog.text


@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_http_error_logs_only_allowlisted_response_shape(monkeypatch, caplog):
    private_phone = "09123456789"
    private_token = "private-token-value"
    private_message = "private provider detail"

    def fail(*args, **kwargs):
        body = {
            "errors": [{"message": private_message, "customer_phone": private_phone}],
            "meta": {"error_code": "2401", "access_token": private_token},
        }
        raise HTTPError(
            "https://console.melipayamak.com/api/send/simple/test-console-token",
            400,
            "bad request",
            hdrs=None,
            fp=BytesIO(json.dumps(body).encode("utf-8")),
        )

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fail)
    with caplog.at_level("WARNING", logger="apps.accounts.delivery"):
        with pytest.raises(OTPDeliveryError):
            MelipayamakDelivery().send(phone=private_phone, code="123456", purpose="login")

    assert "provider_error_shape=root=dict" in caplog.text
    assert "$.errors:list" in caplog.text
    assert "$.meta:dict" in caplog.text
    assert "$.errors[].message:str" in caplog.text
    assert "$.errors[].other:str" in caplog.text
    assert private_phone not in caplog.text
    assert private_token not in caplog.text
    assert private_message not in caplog.text
    assert "123456" not in caplog.text
    assert "test-console-token" not in caplog.text


def test_safe_provider_error_shape_bounds_depth_and_collection_size():
    response = {
        "errors": [{"detail": {"message": "secret", "customer_name": "private"}}],
        "unknown_sensitive_field_name": "private",
    }

    shape = MelipayamakDelivery._safe_provider_error_shape(response)

    assert shape.startswith("root=dict;fields=")
    assert "$.errors:list" in shape
    assert "$.errors[].detail:dict" in shape
    assert "unknown_sensitive_field_name" not in shape
    assert "secret" not in shape
    assert "private" not in shape


def test_provider_error_classifier_handles_nested_values_and_bounds_depth():
    nested = {"errors": [{"detail": {"message": "sender is not allowed"}}]}
    assert MelipayamakDelivery._classify_provider_error(nested) == "sender"
    assert MelipayamakDelivery._classify_provider_error({"deep": {"deeper": {"x": {"y": {"z": "sender"}}}}}) == "missing_error_detail"
    assert MelipayamakDelivery._safe_provider_error_code(
        {"meta": [{"errorCode": "42"}]}
    ) == 42

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



@override_settings(
    MELIPAYAMAK_API_KEY="test-console-token",
    MELIPAYAMAK_SENDER="5000400004",
    MELIPAYAMAK_TIMEOUT_SECONDS=7,
)
def test_each_otp_purpose_uses_its_own_persian_message(monkeypatch):
    payloads = []

    def fake_urlopen(request, timeout):
        payloads.append(json.loads(request.data.decode("utf-8"))["text"])
        return _FakeResponse({"recId": "1234567890123456", "status": ""})

    monkeypatch.setattr("apps.accounts.delivery.urlopen", fake_urlopen)
    delivery = MelipayamakDelivery()
    for purpose in ("login", "signup", "password_reset"):
        delivery.send(phone="09123456789", code="123456", purpose=purpose)

    assert payloads == [
        "کاربر گرامی، کد ورود شما: 123456\nاین کد را در اختیار هیچ‌کس قرار ندهید.\nVedzmani",
        "کاربر گرامی، کد تأیید ثبت‌نام شما: 123456\nاین کد را در اختیار هیچ‌کس قرار ندهید.\nVedzmani",
        "کاربر گرامی، کد بازیابی رمز عبور شما: 123456\nاین کد را در اختیار هیچ‌کس قرار ندهید.\nVedzmani",
    ]
