"""Session, CSRF, privacy and abuse-resistance behavior of the auth boundary that the other accounts tests do not pin.

Each test asserts effective behavior over HTTP (cookies actually sent, responses actually returned), not that a
setting exists."""

import json
from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps.accounts import ratelimit, services
from apps.accounts.delivery import InMemoryDelivery
from apps.accounts.models import OTPChallenge, User
from apps.cart.models import CartItem
from tests.conftest import ApiClient

pytestmark = pytest.mark.django_db

PHONE = "09123456789"


def error_code(response):
    return response.json()["error"]["code"]


def wrong_code_for(good: str) -> str:
    return "000000" if good != "000000" else "000001"


# ------------------------------------------------------------ forged CSRF --
def _post_json(client, path, data, token):
    return client.post(path, data=json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=token)


@pytest.mark.parametrize("path", ["/api/auth/otp/request/", "/api/auth/otp/verify/", "/api/auth/logout/"])
@pytest.mark.parametrize("kind", ["garbage", "token-from-another-browser"])
def test_a_wrong_csrf_token_is_rejected_even_when_a_real_cookie_is_present(api, path, kind):
    api.client.get("/api/auth/csrf/")  # this browser has a genuine csrftoken cookie
    token = "x" * 64 if kind == "garbage" else ApiClient()._token()
    response = _post_json(api.client, path, {"phone": PHONE, "code": "123456"}, token)
    assert response.status_code == 403 and error_code(response) == "csrf_failed"
    assert not InMemoryDelivery.outbox and not OTPChallenge.objects.exists()


def test_authenticated_mutation_with_a_forged_csrf_token_is_rejected(api, make_variant_size):
    vs = make_variant_size()
    api.login(PHONE)
    response = _post_json(api.client, "/api/cart/items/", {"variant_size_id": vs.id}, "x" * 64)
    assert response.status_code == 403 and error_code(response) == "csrf_failed"
    assert not CartItem.objects.exists()
    ok = api.post("/api/cart/items/", {"variant_size_id": vs.id})  # the same request with the real token works
    assert ok.status_code in (200, 201)


# --------------------------------------------------- effective cookie flags --
def test_development_cookies_are_not_secure_so_local_http_keeps_working(api):
    login = api.login(PHONE)
    assert not login.cookies["sessionid"]["secure"] and login.cookies["sessionid"]["httponly"]


def test_production_style_cookie_flags_on_the_real_responses(api, settings):
    settings.SESSION_COOKIE_SECURE = True
    settings.CSRF_COOKIE_SECURE = True
    assert api.get("/api/auth/csrf/").cookies["csrftoken"]["secure"]
    login = api.login(PHONE)
    session_cookie, csrf_cookie = login.cookies["sessionid"], login.cookies["csrftoken"]  # csrf is rotated on login
    assert session_cookie["secure"] and session_cookie["httponly"] and session_cookie["samesite"] == "Lax"
    assert csrf_cookie["secure"] and csrf_cookie["samesite"] == "Lax"


def test_behind_the_https_proxy_forwarded_protocol_prevents_redirect_loops(settings):
    """Nginx talks plain HTTP to Django and sets X-Forwarded-Proto; prod settings trust exactly that header."""
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    settings.SECURE_SSL_REDIRECT = True
    settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = True
    client = Client()
    via_proxy = client.get("/api/auth/csrf/", HTTP_X_FORWARDED_PROTO="https")
    assert via_proxy.status_code == 200 and via_proxy.cookies["csrftoken"]["secure"]
    direct_http = client.get("/api/auth/csrf/")
    assert direct_http.status_code == 301 and direct_http["Location"].startswith("https://")


# ----------------------------------------------------------- session expiry --
def test_an_expired_session_is_rejected_server_side(api):
    api.login(PHONE)
    assert api.get("/api/auth/me/").status_code == 200
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
    assert api.get("/api/auth/me/").status_code == 401


@pytest.mark.parametrize("remember_me", [False, True])
def test_session_lifetime_on_the_cookie_and_in_the_database(api, settings, remember_me):
    login = api.login(PHONE, remember_me=remember_me)
    cookie = login.cookies["sessionid"]
    db_remaining = (Session.objects.get().expire_date - timezone.now()).total_seconds()
    if remember_me:
        assert abs(int(cookie["max-age"]) - settings.AUTH_REMEMBER_ME_SECONDS) < 5
        assert abs(db_remaining - settings.AUTH_REMEMBER_ME_SECONDS) < 5
    else:
        # The browser drops the cookie at close, but the server row (what a stolen cookie would use) lives for
        # SESSION_COOKIE_AGE. Documented in AUTH.md; this pins it so a change is a conscious one.
        assert cookie["max-age"] == "" and cookie["expires"] == ""
        assert abs(db_remaining - settings.SESSION_COOKIE_AGE) < 5


# ------------------------------------------------- privacy: no disclosure --
def test_wrong_code_answers_are_identical_for_known_unknown_and_never_requested_phones(api):
    User.objects.create_user("+989125550000")
    answers = []
    for phone, requested in [("09125550000", True), ("09125550001", True), ("09125550002", False)]:
        if requested:
            assert api.request_otp(phone).status_code == 202
            bad = wrong_code_for(api.last_code())
        else:
            bad = "123456"
        response = api.verify(bad, phone)
        answers.append((response.status_code, response.json()))
        assert phone not in response.content.decode() and bad not in response.content.decode()
    assert len({json.dumps(a, sort_keys=True) for a in answers}) == 1, answers


def test_a_disabled_account_is_only_revealed_to_someone_holding_a_valid_code(api):
    User.objects.create_user("+989123456789", is_active=False)
    api.request_otp(PHONE)
    wrong = api.verify(wrong_code_for(api.last_code()))
    assert wrong.status_code == 400 and error_code(wrong) == "otp_invalid"  # not account_disabled


def test_invalid_phone_validation_error_does_not_echo_input(api):
    response = api.request_otp("not-a-phone-9876")
    assert response.status_code == 400 and "9876" not in response.content.decode()


# ---------------------------------------------------------------- abuse --
def test_verify_ip_limit_tells_the_client_when_to_retry(api, settings):
    settings.OTP_VERIFY_IP_LIMIT = 1
    api.verify("123456")
    blocked = api.verify("123456")
    assert blocked.status_code == 429 and error_code(blocked) == "rate_limited"
    assert int(blocked["Retry-After"]) == settings.OTP_VERIFY_IP_WINDOW_SECONDS


def test_guessing_budget_per_phone_is_bounded_by_request_limit_times_max_attempts(api, settings):
    """A fresh challenge resets the attempt counter, so the hourly request limit is what bounds guessing:
    OTP_REQUEST_PHONE_LIMIT x OTP_MAX_ATTEMPTS wrong guesses per phone per hour, however many IPs are used."""
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    settings.OTP_VERIFY_IP_LIMIT = 10_000  # isolate the per-phone bound from the per-IP limit
    guesses = 0
    for _ in range(settings.OTP_REQUEST_PHONE_LIMIT):
        assert api.request_otp().status_code == 202
        bad = wrong_code_for(api.last_code())
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            assert error_code(api.verify(bad)) == "otp_invalid"
            guesses += 1
        locked = api.verify(bad)
        assert locked.status_code == 429 and error_code(locked) == "otp_attempts_exceeded"
    assert guesses == settings.OTP_REQUEST_PHONE_LIMIT * settings.OTP_MAX_ATTEMPTS
    blocked = api.request_otp()
    assert blocked.status_code == 429 and error_code(blocked) == "rate_limited"


# ----------------------------------------------------- limiter unavailable --
class _BrokenCache:
    """Stands in for an unreachable Redis; the message must never reach a client."""

    def _boom(self, *args, **kwargs):
        raise ConnectionError("redis down: internal-host.example.invalid:6379")

    add = incr = set = get = _boom


def test_otp_request_fails_closed_when_the_rate_limit_store_is_down(monkeypatch):
    monkeypatch.setattr(ratelimit, "cache", _BrokenCache())
    with pytest.raises(ConnectionError):
        services.request_otp(phone="+989123456789", purpose="login", ip="203.0.113.9")
    assert not InMemoryDelivery.outbox and not OTPChallenge.objects.exists()  # nothing created, nothing sent


def test_otp_verify_fails_closed_when_the_rate_limit_store_is_down(monkeypatch):
    services.request_otp(phone="+989123456789", purpose="login", ip="203.0.113.9")
    code = InMemoryDelivery.outbox[-1]["code"]
    monkeypatch.setattr(ratelimit, "cache", _BrokenCache())
    with pytest.raises(ConnectionError):
        services.verify_otp(phone="+989123456789", purpose="login", code=code, ip="203.0.113.9")
    challenge = OTPChallenge.objects.get()
    assert challenge.consumed_at is None and not User.objects.exists()  # no login without the abuse controls


def test_a_rate_limit_store_outage_never_leaks_internals_or_signs_anyone_in(monkeypatch):
    monkeypatch.setattr(ratelimit, "cache", _BrokenCache())
    api = ApiClient()
    api.client = Client(enforce_csrf_checks=True, raise_request_exception=False)
    cache.clear()  # (the real cache; the limiter uses the broken one)
    request = api.request_otp()
    verify = api.verify("123456")
    for response in (request, verify):
        assert response.status_code >= 500
        assert "redis" not in response.content.decode().lower() and "internal-host" not in response.content.decode()
    assert api.get("/api/auth/me/").status_code == 401 and not InMemoryDelivery.outbox
