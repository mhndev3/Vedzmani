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


def test_nginx_blocks_public_django_admin_but_keeps_api_routing_separate():
    conf = NGINX.read_text(encoding="utf-8")
    location = re.search(r"location\s+\^~\s+/admin/\s*\{(.*?)\}", conf, re.DOTALL)
    assert location, "public Django Admin must be blocked"
    assert "return 404" in location.group(1)
    assert "proxy_pass" not in location.group(1)
    # The storefront management API remains a separate route and must not be swallowed by /admin/.
    assert re.search(r"location\s+/api/\s*\{\s*proxy_pass http://backend;", conf)
