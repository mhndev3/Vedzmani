"""Static guards for the production stack files and the Cloudflare real-IP tooling.

No Docker, no network, no database. These tests read repository files only. The runtime behavior of the Nginx
configuration (nginx -t, real-IP handling through a proxy hop) is covered separately by
scripts/validate_prod_stack.py, which needs Docker and runs as its own CI job.
"""

import datetime as dt
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.prod.yml"
DEV_COMPOSE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.production.example"
PROD_CONF = REPO_ROOT / "nginx" / "prod.conf"
DEV_CONF = REPO_ROOT / "nginx" / "default.conf"
REALIP = REPO_ROOT / "nginx" / "cloudflare-realip.conf"
SCRIPT = REPO_ROOT / "scripts" / "cloudflare_realip.py"
FIXTURE_V4 = REPO_ROOT / "scripts" / "testdata" / "cloudflare-ips-v4.fixture.txt"
FIXTURE_V6 = REPO_ROOT / "scripts" / "testdata" / "cloudflare-ips-v6.fixture.txt"

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in (COMPOSE, DEV_COMPOSE, ENV_EXAMPLE, PROD_CONF, DEV_CONF, REALIP, SCRIPT, FIXTURE_V4, FIXTURE_V6)),
    reason="repository root files are not available (backend tests run outside a full checkout)",
)


@pytest.fixture(scope="module")
def cf():
    spec = importlib.util.spec_from_file_location("cloudflare_realip", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses needs the module registered while it executes
    spec.loader.exec_module(module)
    return module


def _without_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _service_block(text: str, name: str) -> str:
    match = re.search(rf"^  {re.escape(name)}:\n((?:    .*\n|\n)+)", text, re.MULTILINE)
    assert match, f"service {name!r} not found in docker-compose.prod.yml"
    return match.group(1)


# ----------------------------------------------------------------------------- docker-compose.prod.yml

def test_only_nginx_publishes_ports_and_only_80_and_443():
    text = COMPOSE.read_text(encoding="utf-8")
    for service in ("postgres", "redis", "backend", "frontend", "migrate", "migrate-plan"):
        block = _without_comments(_service_block(text, service))
        assert not re.search(r"^\s+ports:", block, re.MULTILINE), f"{service} must stay on the internal network"
    nginx_block = _without_comments(_service_block(text, "nginx"))
    published = re.findall(r'^\s+- "([^"]+)"\s*$', nginx_block.split("volumes:")[0], re.MULTILINE)
    assert sorted(published) == ["443:443", "80:80"]


def test_images_are_pinned_and_app_images_use_the_release_tag():
    text = COMPOSE.read_text(encoding="utf-8")
    images = re.findall(r"^\s+image:\s*(\S+)\s*$", text, re.MULTILINE)
    assert images
    for image in images:
        assert ":" in image and not image.endswith(":latest"), f"{image!r} must carry an explicit, non-latest tag"
    assert "vedzmani-backend:${RELEASE_TAG:?" in text and "vedzmani-frontend:${RELEASE_TAG:?" in text


def test_env_template_defines_every_variable_compose_requires():
    required = set(re.findall(r"\$\{([A-Z0-9_]+):\?", COMPOSE.read_text(encoding="utf-8")))
    defined = {
        line.split("=", 1)[0]
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert required, "no required variables found; the pattern in this test may be stale"
    assert required <= defined, f"missing from .env.production.example: {sorted(required - defined)}"


def test_env_template_holds_placeholders_for_secrets_only():
    values = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    for key in ("RELEASE_TAG", "POSTGRES_PASSWORD", "DJANGO_SECRET_KEY"):
        assert values[key].startswith("<") and values[key].endswith(">"), f"{key} must stay a <placeholder>"


# ----------------------------------------------------------------------------------- nginx/prod.conf

def test_prod_nginx_includes_the_file_that_compose_mounts():
    conf = _without_comments(PROD_CONF.read_text(encoding="utf-8"))
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "include /etc/nginx/cloudflare-realip.conf;" in conf
    assert "./nginx/cloudflare-realip.conf:/etc/nginx/cloudflare-realip.conf:ro" in compose


def test_product_media_is_shared_with_backend_and_served_by_nginx():
    compose = COMPOSE.read_text(encoding="utf-8")
    backend = _without_comments(_service_block(compose, "backend"))
    nginx = _without_comments(_service_block(compose, "nginx"))
    conf = _without_comments(PROD_CONF.read_text(encoding="utf-8"))

    assert "${PRODUCT_MEDIA_DIR:-/home/vzinfra/prod/media}:/app/media" in backend
    assert "${PRODUCT_MEDIA_DIR:-/home/vzinfra/prod/media}:/var/www/vedzmani-media:ro" in nginx
    assert "location ^~ /media/" in conf
    assert "alias /var/www/vedzmani-media/;" in conf
    assert 'MEDIA_ROOT = Path(env("MEDIA_ROOT"' in (REPO_ROOT / "backend/config/settings/base.py").read_text(encoding="utf-8")


def test_dev_product_media_is_shared_with_backend_and_served_by_nginx():
    compose = DEV_COMPOSE.read_text(encoding="utf-8")
    backend = _without_comments(_service_block(compose, "backend"))
    nginx = _without_comments(_service_block(compose, "nginx"))
    conf = _without_comments(DEV_CONF.read_text(encoding="utf-8"))

    assert "product_media:/app/media" in backend
    assert "product_media:/var/www/vedzmani-media:ro" in nginx
    assert "location ^~ /media/" in conf
    assert "alias /var/www/vedzmani-media/;" in conf


def test_prod_nginx_never_forwards_client_supplied_addresses():
    conf = _without_comments(PROD_CONF.read_text(encoding="utf-8"))
    # Overwrite, never append: $proxy_add_x_forwarded_for would keep whatever the client sent.
    assert "$proxy_add_x_forwarded_for" not in conf
    assert re.search(r"proxy_set_header\s+X-Forwarded-For\s+\$remote_addr;", conf)
    assert not re.search(r"proxy_set_header\s+\S+\s+\$http_(x_forwarded_for|cf_connecting_ip|x_real_ip)", conf)
    # Which peers are trusted is decided only by the generated include, never inline in prod.conf.
    assert "set_real_ip_from" not in conf and "real_ip_header" not in conf


def test_prod_nginx_redirect_target_is_fixed_and_unknown_tls_names_are_rejected():
    conf = _without_comments(PROD_CONF.read_text(encoding="utf-8"))
    assert re.search(r"return 301 https://vedzmani\.ir\$request_uri;", conf)
    assert not re.search(r"return 30[12] https?://\$host", conf), "a $host redirect would be an open redirect"
    assert "ssl_reject_handshake on;" in conf


# -------------------------------------------------------------------------- committed real-IP include

def test_committed_realip_file_is_valid_and_its_state_is_reported_honestly(cf):
    """Either an inert placeholder or a fully valid generated file. Never a half-edited one."""
    result = cf.check_text(REALIP.read_text(encoding="utf-8"))
    assert result.ok, result.problems
    assert result.status in {"placeholder", "populated"}


# ----------------------------------------------------------------------------------- the generator

def _lists(cf):
    v4 = cf.parse_ranges(FIXTURE_V4.read_text(encoding="utf-8"), 4, source="v4")
    v6 = cf.parse_ranges(FIXTURE_V6.read_text(encoding="utf-8"), 6, source="v6")
    return v4, v6


def test_fixture_lists_parse_and_render_a_file_that_passes_its_own_check(cf):
    v4, v6 = _lists(cf)
    assert (len(v4), len(v6)) == (15, 7)
    text = cf.render(v4, v6, generated_on=dt.date(2026, 10, 28))
    result = cf.check_text(text, require_populated=True, max_age_days=45, today=dt.date(2026, 11, 1))
    assert result.ok and result.status == "populated" and len(result.ranges) == 22
    assert text.count("set_real_ip_from ") == 22
    assert "real_ip_header CF-Connecting-IP;" in text and "real_ip_recursive off;" in text


@pytest.mark.parametrize(
    "line, version",
    [
        ("0.0.0.0/0", 4),  # trusts the whole internet: any client could pick its own address
        ("8.0.0.0/7", 4),  # public but far broader than anything Cloudflare publishes
        ("10.0.0.0/8", 4),
        ("172.16.0.0/12", 4),  # Docker bridge networks live here
        ("192.168.0.0/16", 4),
        ("127.0.0.0/8", 4),
        ("169.254.0.0/16", 4),
        ("100.64.0.0/10", 4),
        ("203.0.113.0/24", 4),  # documentation range
        ("104.16.0.1/13", 4),  # host bits set
        ("173.245.48.0", 4),  # not CIDR
        ("<html>502 Bad Gateway</html>", 4),
        ("2400:cb00::/32", 4),  # IPv6 range in the IPv4 list
        ("::/0", 6),
        ("fc00::/7", 6),
        ("fe80::/10", 6),
        ("173.245.48.0/20", 6),  # IPv4 range in the IPv6 list
    ],
)
def test_parse_ranges_rejects_unsafe_or_malformed_lines(cf, line, version):
    with pytest.raises(cf.RangeError):
        cf.parse_ranges(line + "\n", version)


def test_parse_ranges_rejects_short_and_empty_lists(cf):
    with pytest.raises(cf.RangeError):
        cf.parse_ranges("\n".join(FIXTURE_V4.read_text(encoding="utf-8").splitlines()[:4]), 4)
    with pytest.raises(cf.RangeError):
        cf.parse_ranges("\n\n", 4)


def test_fetch_refuses_plain_http_before_any_network_use(cf):
    with pytest.raises(cf.RangeError):
        cf.fetch("http://www.cloudflare.com/ips-v4")


def test_generate_writes_atomically_and_never_replaces_a_good_file_with_a_bad_one(cf, tmp_path, capsys):
    out = tmp_path / "realip.conf"
    args = ["generate", "--v4-file", str(FIXTURE_V4), "--v6-file", str(FIXTURE_V6), "--generated-on", "2026-10-28",
            "--output", str(out)]
    assert cf.main(args) == 0
    good = out.read_text(encoding="utf-8")
    v4, v6 = _lists(cf)
    assert good == cf.render(v4, v6, generated_on=dt.date(2026, 10, 28))

    bad = tmp_path / "bad-v4.txt"
    bad.write_text("0.0.0.0/0\n", encoding="utf-8")
    assert cf.main(["generate", "--v4-file", str(bad), "--v6-file", str(FIXTURE_V6), "--output", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == good, "a failed run must leave the previous file untouched"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad-v4.txt", "realip.conf"], "no temp files may be left behind"
    assert "Nothing was written" in capsys.readouterr().err


# ------------------------------------------------------------------------------------- the checker

def _good_text(cf):
    v4, v6 = _lists(cf)
    return cf.render(v4, v6, generated_on=dt.date(2026, 10, 28))


def test_comment_only_file_is_a_placeholder_and_can_be_required_to_be_populated(cf):
    text = "# nothing configured\n\n"
    assert cf.check_text(text).status == "placeholder" and cf.check_text(text).ok
    strict = cf.check_text(text, require_populated=True)
    assert not strict.ok and "NOT active" in strict.problems[0]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t.replace("real_ip_header CF-Connecting-IP;", "real_ip_header X-Forwarded-For;"),
        lambda t: t.replace("real_ip_header CF-Connecting-IP;\n", ""),  # nginx would fall back to X-Real-IP
        lambda t: t.replace("real_ip_recursive off;", "real_ip_recursive on;"),
        lambda t: t + "allow all;\n",
        lambda t: t + "set_real_ip_from 0.0.0.0/0;\n",
        lambda t: t + "set_real_ip_from 10.0.0.0/8;\n",
        lambda t: t + "set_real_ip_from 173.245.48.0/20;\n",  # duplicate
        lambda t: t.replace("set_real_ip_from 173.245.48.0/20;", "set_real_ip_from 173.245.48.0/20"),  # no semicolon
    ],
)
def test_check_rejects_unsafe_or_corrupted_includes(cf, mutate):
    assert not cf.check_text(mutate(_good_text(cf))).ok


def test_check_rejects_truncated_range_lists(cf):
    lines = [line for line in _good_text(cf).splitlines() if not line.startswith("set_real_ip_from 2")]
    assert not cf.check_text("\n".join(lines)).ok  # all IPv6 ranges missing


def test_check_flags_stale_or_undated_files_only_when_asked(cf):
    text = _good_text(cf)
    today = dt.date(2026, 12, 31)
    assert cf.check_text(text, today=today).ok
    assert not cf.check_text(text, max_age_days=45, today=today).ok
    undated = "\n".join(line for line in text.splitlines() if "Generated:" not in line)
    assert not cf.check_text(undated, max_age_days=45, today=today).ok


# ------------------------------------------------------------- proxy and health-check contracts (static)

def _example_values() -> dict:
    values = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_proxy_contract_between_compose_nginx_and_django_settings():
    compose = COMPOSE.read_text(encoding="utf-8")
    backend = _without_comments(_service_block(compose, "backend"))
    # One trusted hop (this Nginx), which overwrites X-Forwarded-For with the verified client address.
    assert re.search(r'AUTH_TRUSTED_PROXY_COUNT:\s*"1"', backend)
    assert re.search(r'DJANGO_SECURE_SSL_REDIRECT:\s*"true"', backend)
    # Nginx terminates TLS and tells Django so; SECURE_PROXY_SSL_HEADER in prod.py trusts exactly this header.
    assert re.search(r"proxy_set_header\s+X-Forwarded-Proto\s+\$scheme;", _without_comments(PROD_CONF.read_text(encoding="utf-8")))
    prod_py = (REPO_ROOT / "backend" / "config" / "settings" / "prod.py").read_text(encoding="utf-8")
    assert 'SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")' in prod_py


def test_health_check_contracts_match_the_code_they_call():
    compose = COMPOSE.read_text(encoding="utf-8")
    values = _example_values()
    hosts = values["DJANGO_ALLOWED_HOSTS"].split(",")
    # Backend: the check sends PRIMARY_HOST as Host, so it must be an allowed host; /api/health/ is exempt from the
    # HTTPS redirect (prod.py), otherwise a plain-HTTP check inside the container would be redirected.
    backend = _service_block(compose, "backend")
    assert "/api/health/" in backend and "${PRIMARY_HOST:-vedzmani.ir}" in backend
    assert values["PRIMARY_HOST"] in hosts and "vedzmani.ir" in hosts
    assert 'SECURE_REDIRECT_EXEMPT = [r"^api/health/"]' in (REPO_ROOT / "backend/config/settings/prod.py").read_text(encoding="utf-8")
    # Frontend: the server-side API calls use http://backend:8000, so Django sees Host "backend:8000".
    assert "API_INTERNAL_URL: http://backend:8000" in compose
    assert "backend" in hosts
    frontend = _service_block(compose, "frontend")
    assert "/healthz" in frontend and (REPO_ROOT / "frontend/src/app/healthz/route.ts").is_file()
    # Nginx: the check hits the port-80 server's /nginx-health, which must exist there.
    nginx = _service_block(compose, "nginx")
    assert "/nginx-health" in nginx
    conf = _without_comments(PROD_CONF.read_text(encoding="utf-8"))
    assert re.search(r"listen 80 default_server;.*?location = /nginx-health\s*\{[^}]*return 200", conf, re.DOTALL)
    # Start order follows health.
    assert re.search(r"backend:\s*\{\s*condition:\s*service_healthy\s*\}", nginx)
    assert re.search(r"frontend:\s*\{\s*condition:\s*service_healthy\s*\}", nginx)


def _prod_settings_env() -> dict:
    """Environment for config.settings.prod built from the template, with dummies for every placeholder."""
    env = {k: v for k, v in _example_values().items()}
    for key, value in list(env.items()):
        if value.startswith("<"):
            env[key] = "ci-validation-placeholder-0123456789abcdef-0123456789"
    env["DATABASE_URL"] = f"postgres://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}@postgres:5432/{env['POSTGRES_DB']}"
    env["REDIS_URL"] = "redis://redis:6379/0"
    env.update({"DJANGO_SETTINGS_MODULE": "config.settings.prod", "AUTH_TRUSTED_PROXY_COUNT": "1",
                "DJANGO_SECURE_SSL_REDIRECT": "true"})
    return env


def test_django_prod_settings_honor_the_proxy_and_health_contract():
    """Real Django under config.settings.prod (no database or Redis connection is opened by these requests)."""
    import json
    import os
    import subprocess

    code = (
        "import json, django\n"
        "django.setup()\n"
        "from django.test import Client\n"
        "c = Client()\n"
        "out = {}\n"
        "out['health_primary_http'] = c.get('/api/health/', HTTP_HOST='vedzmani.ir').status_code\n"
        "out['health_backend_host'] = c.get('/api/health/', HTTP_HOST='backend:8000').status_code\n"
        "out['health_unknown_host'] = c.get('/api/health/', HTTP_HOST='evil.example').status_code\n"
        "out['health_forwarded_https'] = c.get('/api/health/', HTTP_HOST='vedzmani.ir', HTTP_X_FORWARDED_PROTO='https').status_code\n"
        "r = c.get('/api/catalog/products/', HTTP_HOST='vedzmani.ir')\n"
        "out['other_path_http'] = [r.status_code, r.headers.get('Location')]\n"
        "print('RESULT ' + json.dumps(out))\n"
    )
    env = {**{k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME"}}, **_prod_settings_env()}
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT / "backend", env=env, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    out = json.loads(next(line for line in result.stdout.splitlines() if line.startswith("RESULT "))[7:])
    assert out["health_primary_http"] == 200, "the compose health check (plain HTTP, Host vedzmani.ir) must pass"
    assert out["health_backend_host"] == 200, "server-side calls from the frontend use Host backend:8000"
    assert out["health_unknown_host"] == 400
    assert out["health_forwarded_https"] == 200
    assert out["other_path_http"] == [301, "https://vedzmani.ir/api/catalog/products/"]


# ---------------------------------------------------- real-IP generator: IPv4 + IPv6, placeholder behavior

def test_generated_include_contains_both_ipv4_and_ipv6_ranges(cf):
    v4, v6 = _lists(cf)
    text = cf.render(v4, v6, generated_on=dt.date(2026, 10, 28))
    result = cf.check_text(text, require_populated=True)
    assert result.ok
    assert sum(1 for n in result.ranges if n.version == 4) == 15
    assert sum(1 for n in result.ranges if n.version == 6) == 7
    assert re.search(r"^set_real_ip_from 2606:4700::/32;$", text, re.MULTILINE)
    assert re.search(r"^set_real_ip_from 173\.245\.48\.0/20;$", text, re.MULTILINE)


def test_cli_check_fails_the_committed_placeholder_when_population_is_required(cf, capsys):
    placeholder = cf.check_text(REALIP.read_text(encoding="utf-8")).status == "placeholder"
    code = cf.main(["check", str(REALIP), "--require-populated"])
    captured = capsys.readouterr()
    if placeholder:
        assert code == 1 and "NOT active" in captured.err
    else:
        assert code == 0
    assert cf.main(["check", str(REALIP)]) == 0  # without the flag a placeholder is reported, not failed


def test_image_build_collects_static_files_under_prod_settings_before_serving():
    """Root cause of the CI 500s on /admin/login/ (2026-10-29): WhiteNoise's manifest storage raises
    "Missing staticfiles manifest entry" when `collectstatic` has not run. The image must therefore run it at build
    time with prod settings, and prod settings must keep using the manifest storage that this step feeds."""
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    prod_settings = (REPO_ROOT / "backend" / "config" / "settings" / "prod.py").read_text(encoding="utf-8")
    assert re.search(r"DJANGO_SETTINGS_MODULE=config\.settings\.prod[\s\\]+(?:\S+=\S+[\s\\]+)*python manage\.py collectstatic --noinput", dockerfile)
    assert dockerfile.index("collectstatic") < dockerfile.index("CMD [")
    assert "whitenoise.storage.CompressedManifestStaticFilesStorage" in prod_settings
    assert "mkdir -p /app/staticfiles /app/media" in dockerfile
    assert "chown app:app /app/staticfiles /app/media" in dockerfile