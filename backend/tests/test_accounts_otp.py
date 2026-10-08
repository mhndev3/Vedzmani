from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.delivery import InMemoryDelivery
from apps.accounts.models import OTPChallenge, User

pytestmark = pytest.mark.django_db

PHONE = "09123456789"
CANON = "+989123456789"


def error_code(response):
    return response.json()["error"]["code"]


# ---------------------------------------------------------------- request --
def test_valid_otp_request_sends_code_and_stores_only_a_hash(api):
    response = api.request_otp(PHONE)
    assert response.status_code == 202
    assert len(InMemoryDelivery.outbox) == 1
    sent = InMemoryDelivery.outbox[0]
    assert sent["phone"] == CANON and sent["code"].isdigit() and len(sent["code"]) == 6

    challenge = OTPChallenge.objects.get()
    assert challenge.phone == CANON and challenge.purpose == "login"
    assert challenge.attempt_count == 0 and challenge.consumed_at is None
    assert len(challenge.code_hash) == 64 and sent["code"] not in challenge.code_hash
    ttl = challenge.expires_at - challenge.created_at
    assert timedelta(seconds=290) < ttl <= timedelta(seconds=301)


def test_invalid_phone_rejected_before_anything_is_sent(api):
    response = api.request_otp("12345")
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]["phone"][0]["code"] == "invalid_phone"
    assert not InMemoryDelivery.outbox and not OTPChallenge.objects.exists()


def test_request_response_is_identical_for_known_and_unknown_phones(api):
    User.objects.create_user("09125550000")
    known = api.request_otp("09125550000")
    unknown = api.request_otp("09125550001")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_resend_cooldown_is_rate_limited(api):
    assert api.request_otp().status_code == 202
    again = api.request_otp()
    assert again.status_code == 429 and error_code(again) == "rate_limited"
    assert int(again["Retry-After"]) > 0
    assert len(InMemoryDelivery.outbox) == 1


def test_per_phone_hourly_limit(api, settings):
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    settings.OTP_REQUEST_PHONE_LIMIT = 2
    assert [api.request_otp().status_code for _ in range(3)] == [202, 202, 429]


def test_per_ip_hourly_limit_across_phones(api, settings):
    settings.OTP_REQUEST_IP_LIMIT = 2
    codes = [api.request_otp(f"0912000000{i}").status_code for i in range(3)]
    assert codes == [202, 202, 429]


def test_new_code_invalidates_the_previous_one(api, settings, monkeypatch):
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    values = iter([111111, 222222])
    monkeypatch.setattr("apps.accounts.services.secrets.randbelow", lambda n: next(values))
    api.request_otp()
    api.request_otp()
    assert api.verify("111111").status_code == 400
    assert api.verify("222222").status_code == 200


def test_delivery_failure_is_reported_and_never_faked(api, settings):
    settings.OTP_DELIVERY_BACKEND = "apps.accounts.delivery.UnconfiguredDelivery"
    response = api.request_otp()
    assert response.status_code == 503 and error_code(response) == "otp_delivery_unavailable"
    assert not OTPChallenge.objects.filter(expires_at__gt=timezone.now()).exists()


# ----------------------------------------------------------------- verify --
def test_valid_otp_verifies_and_creates_user(api):
    api.request_otp()
    response = api.verify(api.last_code())
    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is True and body["user"]["phone"] == CANON
    assert "code" not in body and "password" not in str(body)
    assert OTPChallenge.objects.get().consumed_at is not None


def test_wrong_code_counts_an_attempt(api):
    api.request_otp()
    wrong = "000000" if api.last_code() != "000000" else "000001"
    response = api.verify(wrong)
    assert response.status_code == 400 and error_code(response) == "otp_invalid"
    assert OTPChallenge.objects.get().attempt_count == 1
    assert not User.objects.exists()


def test_malformed_code_is_a_validation_error(api):
    api.request_otp()
    response = api.verify("12ab")
    assert response.status_code == 400 and error_code(response) == "validation_error"


def test_verify_without_any_challenge_is_invalid(api):
    response = api.verify("123456")
    assert response.status_code == 400 and error_code(response) == "otp_invalid"


def test_expired_code_is_rejected(api):
    api.request_otp()
    OTPChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    response = api.verify(api.last_code())
    assert response.status_code == 400 and error_code(response) == "otp_expired"
    assert not User.objects.exists()


def test_code_is_single_use_and_replay_is_rejected(api):
    api.request_otp()
    code = api.last_code()
    assert api.verify(code).status_code == 200
    api.post("/api/auth/logout/")
    replay = api.verify(code)
    assert replay.status_code == 400 and error_code(replay) == "otp_consumed"
    assert api.get("/api/auth/me/").status_code == 401


def test_too_many_attempts_locks_out_even_the_correct_code(api, settings):
    api.request_otp()
    good = api.last_code()
    bad = "000000" if good != "000000" else "000001"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert error_code(api.verify(bad)) == "otp_invalid"
    locked = api.verify(good)
    assert locked.status_code == 429 and error_code(locked) == "otp_attempts_exceeded"
    assert not User.objects.exists()


def test_verify_ip_brute_force_limit(api, settings):
    settings.OTP_VERIFY_IP_LIMIT = 3
    statuses = [api.verify("123456").status_code for _ in range(4)]
    assert statuses == [400, 400, 400, 429]


def test_persian_digits_in_code_are_accepted(api):
    api.request_otp()
    persian = api.last_code().translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    assert api.verify(persian).status_code == 200
