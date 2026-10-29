"""Production proxy/redirect contract (prod settings, exercised in a subprocess; no database or Redis contact).

These tests pin what `config.settings.prod` does today with the `X-Forwarded-Proto` header and the `Host` header on the
health endpoints. They do NOT decide the production TLS topology: see docs/PRODUCTION_DEPLOYMENT.md
("TLS termination: owner decision"). They run against the settings on this branch, not against any infrastructure
proposal (e.g. the open production-stack PR) and not against a running proxy.

Two independent gates apply to every request under prod settings:
1. `SECURE_SSL_REDIRECT` (path-based; `SECURE_REDIRECT_EXEMPT` = `^api/health/`) looks at `X-Forwarded-Proto`.
2. `ALLOWED_HOSTS` (host-based; no exemption) looks at `Host`. The health exemption does NOT bypass it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOST = "shop.example.test"

# argv: path, X-Forwarded-Proto value ("" = header absent), Host header value.
_PROBE = """
import json, sys
import django
django.setup()
from django.test import Client
path, proto, host = sys.argv[1], sys.argv[2], sys.argv[3]
extra = {"HTTP_HOST": host}
if proto:
    extra["HTTP_X_FORWARDED_PROTO"] = proto
r = Client(raise_request_exception=False).get(path, **extra)
print(json.dumps({"status": r.status_code, "location": r.headers.get("Location", "")}))
"""


def _get_under_prod_settings(
    path: str, forwarded_proto: str = "", host: str = HOST, allowed_hosts: str = HOST
) -> dict:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "prod-contract-test-key-not-a-secret-0123456789",
        "DJANGO_ALLOWED_HOSTS": allowed_hosts,
        "DATABASE_URL": "postgres://u:p@127.0.0.1:1/none",
        "REDIS_URL": "redis://127.0.0.1:1/0",
    }
    env.pop("OTP_DELIVERY_BACKEND", None)
    env.pop("DJANGO_SECURE_SSL_REDIRECT", None)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, path, forwarded_proto, host],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_liveness_is_exempt_from_https_redirect_even_when_proxy_says_http():
    """Container/orchestrator health probes speak plain HTTP; a 301 here would mark the backend unhealthy."""
    response = _get_under_prod_settings("/api/health/", forwarded_proto="http")
    assert response["status"] == 200, response


@pytest.mark.parametrize("proto", ["", "http", "https"])
def test_liveness_with_an_allowed_host_is_served_whatever_the_forwarded_proto(proto):
    """The in-container probe may send no `X-Forwarded-Proto` at all; only the Host must be allowed."""
    assert _get_under_prod_settings("/api/health/", forwarded_proto=proto)["status"] == 200


def test_readiness_is_covered_by_the_same_redirect_exemption():
    """`^api/health/` also matches `/api/health/ready/`. With PostgreSQL/Redis unreachable (as here) it answers 503,
    which proves the view ran; the point is that it is never turned into a 301."""
    response = _get_under_prod_settings("/api/health/ready/", forwarded_proto="http")
    assert response["status"] in {200, 503}, response
    assert response["location"] == ""


@pytest.mark.parametrize("path", ["/api/healthz/", "/api/auth/csrf/", "/api/healthy/"])
def test_redirect_exemption_is_limited_to_the_health_prefix(path):
    """Near-miss and other /api/ paths are still redirected when the proxy reports http."""
    response = _get_under_prod_settings(path, forwarded_proto="http")
    assert response["status"] == 301, response
    assert response["location"] == f"https://{HOST}{path}"


@pytest.mark.parametrize(
    "host, proto",
    [("localhost:8000", "http"), ("localhost:8000", ""), ("127.0.0.1:8000", "http"), ("backend:8000", "http")],
)
def test_health_exemption_does_not_bypass_allowed_hosts(host, proto):
    """The exemption is about the HTTPS redirect only. A probe whose Host is not in DJANGO_ALLOWED_HOSTS gets 400.
    This is why the dev Compose check (`http://localhost:8000/api/health/`) cannot be reused unchanged in production."""
    response = _get_under_prod_settings("/api/health/", forwarded_proto=proto, host=host)
    assert response["status"] == 400, response


def test_loopback_probe_passes_when_localhost_is_an_allowed_host():
    """Remediation option 1: add the probe's Host to DJANGO_ALLOWED_HOSTS."""
    response = _get_under_prod_settings(
        "/api/health/", forwarded_proto="", host="localhost:8000", allowed_hosts=f"{HOST},localhost"
    )
    assert response["status"] == 200, response


def test_loopback_probe_passes_when_it_sends_an_allowed_host_header():
    """Remediation option 2: connect to loopback but send `Host: <allowed domain>`; no settings change."""
    assert _get_under_prod_settings("/api/health/", forwarded_proto="", host=HOST)["status"] == 200


def test_server_side_calls_to_backend_need_the_backend_service_name_in_allowed_hosts():
    """The Next.js server calls `http://backend:8000` (API_INTERNAL_URL in docker-compose.yml), so Django sees
    `Host: backend:8000`. ALLOWED_HOSTS matching ignores the port, so listing `backend` is enough; without it those
    calls get 400 (see the parametrized case above)."""
    response = _get_under_prod_settings(
        "/api/health/", forwarded_proto="", host="backend:8000", allowed_hosts=f"{HOST},backend"
    )
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


@pytest.mark.parametrize("proto", ["HTTPS", "http, https", "wss", "1"])
def test_only_the_exact_value_https_counts_as_secure(proto):
    """Django compares the (first) header value to the literal `https`; anything else is treated as plain http."""
    assert _get_under_prod_settings("/admin/login/", forwarded_proto=proto)["status"] == 301


def test_first_value_of_a_comma_separated_forwarded_proto_wins():
    """Django (>= 4.0) reads only the FIRST comma-separated value. A proxy that APPENDS to a client-supplied
    `X-Forwarded-Proto: https` would therefore make the app treat plain HTTP as secure. The proxy in front of the
    backend must OVERWRITE the header (as `proxy_set_header X-Forwarded-Proto ...` does), never append to it."""
    assert _get_under_prod_settings("/admin/login/", forwarded_proto="https, http")["status"] == 200
