"""OTP delivery failure handling: no matter how a provider adapter fails, the customer gets the documented
503 `otp_delivery_unavailable`, the unsent code is never left valid, and nothing is faked or leaked."""

import logging

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts import services
from apps.accounts.delivery import InMemoryDelivery, OTPDelivery, OTPDeliveryError
from apps.accounts.exceptions import DeliveryUnavailable
from apps.accounts.models import OTPChallenge

pytestmark = pytest.mark.django_db

PHONE = "+989123456789"
SECRET_IN_MESSAGE = "https://sms.example.invalid/send?api_key=SHOULD-NEVER-BE-LOGGED&to=09123456789"


class _Failing(OTPDelivery):
    """Test double for a provider adapter. `exc` is what the (mocked) provider raises."""

    exc: Exception = OTPDeliveryError("provider said no")

    def send(self, *, phone, code, purpose):
        raise self.exc


def _use_failing_adapter(monkeypatch, exc):
    adapter = type("FailingAdapter", (_Failing,), {"exc": exc})
    monkeypatch.setattr(services, "get_delivery", lambda: adapter())


@pytest.mark.parametrize(
    "exc",
    [
        OTPDeliveryError("provider said no"),  # the documented adapter contract
        TimeoutError("provider timed out"),  # an adapter that forgot to wrap a transport error
        ConnectionError(SECRET_IN_MESSAGE),
        RuntimeError("unexpected adapter bug"),
    ],
    ids=["documented-error", "timeout", "connection-error", "runtime-error"],
)
def test_any_adapter_failure_is_a_503_and_leaves_no_valid_code(monkeypatch, exc):
    _use_failing_adapter(monkeypatch, exc)
    with pytest.raises(DeliveryUnavailable):
        services.request_otp(phone=PHONE, purpose="login", ip="203.0.113.9")
    # A code that was never delivered must not stay usable.
    assert not OTPChallenge.objects.filter(expires_at__gt=timezone.now(), consumed_at__isnull=True).exists()


def test_api_answers_503_for_an_unexpected_adapter_error(api, monkeypatch):
    _use_failing_adapter(monkeypatch, TimeoutError("provider timed out"))
    response = api.request_otp()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "otp_delivery_unavailable"


def test_adapter_failure_log_does_not_contain_provider_message_phone_or_code(monkeypatch, caplog):
    """Provider exceptions can embed URLs with API keys or the phone number: only the type may be logged."""
    _use_failing_adapter(monkeypatch, ConnectionError(SECRET_IN_MESSAGE))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(DeliveryUnavailable):
            services.request_otp(phone=PHONE, purpose="login", ip="203.0.113.9")
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "OTP delivery failed" in logged
    assert "SHOULD-NEVER-BE-LOGGED" not in logged and "09123456789" not in logged and "989123456789" not in logged


def test_a_working_adapter_after_a_failure_still_delivers(api, monkeypatch):
    """A failed attempt must not poison later requests (new challenge, new code)."""
    _use_failing_adapter(monkeypatch, TimeoutError("down"))
    assert api.request_otp().status_code == 503
    monkeypatch.undo()
    api.client.cookies.clear()
    cache.clear()  # the failed attempt consumed the resend cooldown; this test is about delivery, not limits
    assert api.request_otp().status_code == 202
    assert InMemoryDelivery.outbox[-1]["phone"] == PHONE
