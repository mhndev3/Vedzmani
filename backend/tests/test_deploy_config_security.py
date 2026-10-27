"""Static guards for repository deployment config (no Docker, no network, no database).

Why text checks: PyYAML is not a backend dependency, and these files are tiny. The runtime behavior of the Nginx
throttle was verified separately against a real nginx container; these tests only stop the protections from being
silently removed.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"
NGINX = REPO_ROOT / "nginx" / "default.conf"

pytestmark = pytest.mark.skipif(
    not (COMPOSE.is_file() and NGINX.is_file()),
    reason="repository root files are not available (backend tests run outside a full checkout)",
)


def _service_block(text: str, name: str) -> str:
    """Lines of one top-level service in docker-compose.yml (2-space indented key under `services:`)."""
    match = re.search(rf"^  {re.escape(name)}:\n((?:    .*\n|\n)+)", text, re.MULTILINE)
    assert match, f"service {name!r} not found in docker-compose.yml"
    return match.group(1)


def test_base_compose_publishes_postgres_on_loopback_only():
    """Docker-published ports bypass host firewalls: an unqualified `5433:5432` listens on every interface."""
    block = _service_block(COMPOSE.read_text(encoding="utf-8"), "postgres")
    published = re.findall(r'^\s+- "([^"]+:\d+)"\s*$', block, re.MULTILINE)
    assert published, "postgres no longer publishes a host port; update this test if that is intentional"
    for mapping in published:
        assert mapping.startswith("127.0.0.1:"), f"postgres port {mapping!r} is not bound to 127.0.0.1"


def test_base_compose_does_not_publish_redis_backend_or_frontend():
    text = COMPOSE.read_text(encoding="utf-8")
    for service in ("redis", "backend", "frontend"):
        assert "ports:" not in _service_block(text, service), f"{service} must stay internal to the Compose network"


def test_nginx_throttles_admin_login_posts():
    conf = NGINX.read_text(encoding="utf-8")
    assert re.search(r"limit_req_zone\s+\$admin_login_limit_key\s+zone=admin_login:", conf)
    location = re.search(r"location\s+=\s+/admin/login/\s*\{(.*?)\}", conf, re.DOTALL)
    assert location, "exact-match /admin/login/ location is missing"
    assert "limit_req zone=admin_login" in location.group(1)
    assert "proxy_pass http://backend" in location.group(1)
    # Only POST is keyed, so loading the login page is never throttled.
    assert re.search(r"map\s+\$request_method\s+\$admin_login_limit_key\s*\{[^}]*POST\s+\$binary_remote_addr", conf)
