"""Production proxy/redirect contract (prod settings, exercised in a subprocess; no database or Redis contact).

These tests pin what `config.settings.prod` does today with the `X-Forwarded-Proto` header. They do NOT decide the
production TLS topology: see docs/PRODUCTION_DEPLOYMENT.md ("TLS termination: owner decision").
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOST = "shop.example.test"

_PROBE = """
import json, sys
import django
django.setup()
from django.test import Client
path, proto = sys.argv[1], sys.argv[2]
extra = {"HTTP_HOST": "shop.example.test"}
if proto:
    extra["HTTP_X_FORWARDED_PROTO"] = proto
r = Client(raise_request_exception=False).get(path, **extra)
print(json.dumps({"status": r.status_code, "location": r.headers.get("Location", "")}))
"""


def _get_under_prod_settings(path: str, forwarded_proto: str = "") -> dict:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "prod-contract-test-key-not-a-secret-0123456789",
        "DJANGO_ALLOWED_HOSTS": HOST,
        "DATABASE_URL": "postgres://u:p@127.0.0.1:1/none",
        "REDIS_URL": "redis://127.0.0.1:1/0",
    }
    env.pop("OTP_DELIVERY_BACKEND", None)
    env.pop("DJANGO_SECURE_SSL_REDIRECT", None)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, path, forwarded_proto],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_liveness_is_exempt_from_https_redirect_even_when_proxy_says_http():
    """Container/orchestrator health probes speak plain HTTP; a 301 here would mark the backend unhealthy."""
    response = _get_under_prod_settings("/api/health/", forwarded_proto="http")
    assert response["status"] == 200, response


def test_pages_redirect_to_https_when_proxy_reports_http():
    """Why Nginx sending `$scheme` (always `http` inside the Docker network) behind a TLS-terminating edge loops."""
    response = _get_under_prod_settings("/admin/login/", forwarded_proto="http")
    assert response["status"] == 301, response
    assert response["location"] == f"https://{HOST}/admin/login/"


def test_pages_are_served_when_trusted_proxy_reports_https():
    assert _get_under_prod_settings("/admin/login/", forwarded_proto="https")["status"] == 200


@pytest.mark.parametrize("proto", ["", "http"])
def test_missing_or_http_forwarded_proto_never_counts_as_secure(proto):
    assert _get_under_prod_settings("/admin/login/", forwarded_proto=proto)["status"] == 301
