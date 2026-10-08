import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.db import connections

from apps.accounts import services
from apps.accounts.delivery import InMemoryDelivery
from apps.accounts.exceptions import OTPConsumed
from apps.accounts.models import OTPChallenge, User

BACKEND_DIR = Path(__file__).resolve().parent.parent
PHONE = "09123456789"


# ------------------------------------------------------------------ CSRF --
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/auth/otp/request/", "/api/auth/otp/verify/", "/api/auth/logout/"])
def test_csrf_is_enforced_on_every_post(api, path):
    response = api.post(path, {"phone": PHONE, "code": "123456"}, csrf=False)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert not InMemoryDelivery.outbox


def test_csrf_middleware_is_still_installed():
    assert "django.middleware.csrf.CsrfViewMiddleware" in django_settings.MIDDLEWARE


@pytest.mark.django_db
def test_csrf_endpoint_sets_cookie_and_returns_token(api):
    response = api.get("/api/auth/csrf/")
    assert response.status_code == 200 and response.json()["csrfToken"]
    assert "csrftoken" in response.cookies


# --------------------------------------------------------------- leakage --
@pytest.mark.django_db
def test_responses_never_contain_the_otp_or_its_hash(api):
    response = api.request_otp()
    code = api.last_code()
    challenge = OTPChallenge.objects.get()
    assert response.json() == {"detail": "OTP request accepted."}
    assert code not in response.content.decode()
    assert challenge.code_hash not in response.content.decode()
    verify = api.verify(code)
    assert challenge.code_hash not in verify.content.decode()


def _run_settings(module_env: dict[str, str]):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "x" * 50,
        "DJANGO_ALLOWED_HOSTS": "shop.example.com",
        "DATABASE_URL": "postgres://u:p@localhost:5432/d",
        "REDIS_URL": "redis://localhost:6379/0",
        **module_env,
    }
    if "OTP_DELIVERY_BACKEND" not in module_env:
        env.pop("OTP_DELIVERY_BACKEND", None)
    code = (
        "from django.conf import settings as s; "
        "print(s.SESSION_COOKIE_SECURE, s.SESSION_COOKIE_HTTPONLY, s.SESSION_COOKIE_SAMESITE, "
        "s.CSRF_COOKIE_SECURE, s.OTP_DELIVERY_BACKEND)"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)


def test_production_cookies_secure_and_default_delivery_refuses_to_send():
    result = _run_settings({})
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        "True", "True", "Lax", "True", "apps.accounts.delivery.UnconfiguredDelivery",
    ]


@pytest.mark.parametrize("backend", ["ConsoleDelivery", "InMemoryDelivery"])
def test_production_refuses_to_boot_with_dev_delivery_backends(backend):
    result = _run_settings({"OTP_DELIVERY_BACKEND": f"apps.accounts.delivery.{backend}"})
    assert result.returncode != 0
    assert "must not be used in production" in result.stderr


# ------------------------------------------------------------ client IP --
def test_forwarded_for_is_ignored_unless_proxies_are_trusted(rf, settings):
    from apps.accounts.ratelimit import get_client_ip

    request = rf.get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7")
    settings.AUTH_TRUSTED_PROXY_COUNT = 0
    assert get_client_ip(request) == "10.0.0.5"  # spoofable header not trusted
    settings.AUTH_TRUSTED_PROXY_COUNT = 1
    assert get_client_ip(request) == "198.51.100.7"  # entry appended by our proxy


# ----------------------------------------------------------- concurrency --
def _in_threads(count, fn):
    barrier = threading.Barrier(count)

    def run(i):
        try:
            barrier.wait(timeout=10)
            return fn(i)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


@pytest.mark.django_db(transaction=True)
def test_concurrent_user_creation_for_one_phone_yields_one_user():
    results = _in_threads(8, lambda i: User.objects.get_or_create_by_phone(PHONE))
    assert User.objects.count() == 1
    assert sum(1 for _, created in results if created) == 1
    assert len({user.pk for user, _ in results}) == 1


@pytest.mark.django_db(transaction=True)
def test_otp_cannot_be_consumed_twice_under_concurrency():
    services.request_otp(phone="+989123456789", purpose="login", ip="203.0.113.9")
    code = InMemoryDelivery.outbox[-1]["code"]

    def attempt(i):
        try:
            return services.verify_otp(phone="+989123456789", purpose="login", code=code, ip="203.0.113.9")
        except OTPConsumed:
            return None

    results = _in_threads(6, attempt)
    assert sum(1 for r in results if r is not None) == 1
    assert User.objects.count() == 1
    assert OTPChallenge.objects.get().consumed_at is not None
