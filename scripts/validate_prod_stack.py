#!/usr/bin/env python3
"""Validate docker-compose.prod.yml and nginx/prod.conf in a throwaway environment (standard library + Docker).

What this checks, and what it deliberately does not:

  compose  `docker compose config -q` on docker-compose.prod.yml, using values derived from
           .env.production.example with every <placeholder> replaced by a dummy. This proves the file parses,
           that the template defines every variable Compose requires, and that Compose still fails fast when a
           required variable is missing. It does not start anything and does not read any real .env file.

  nginx    Runs the pinned nginx image (the tag is read from docker-compose.prod.yml) with a freshly generated
           SELF-SIGNED certificate and fake upstream names. It proves that:
             * `nginx -t` accepts nginx/prod.conf with the committed real-IP file and with a generated one,
               and rejects a deliberately broken real-IP file (so the include is really being read);
             * a client cannot choose its own address: from an untrusted peer, CF-Connecting-IP, X-Real-IP and
               X-Forwarded-For are ignored and the backend sees the peer address;
             * from a trusted peer, CF-Connecting-IP is used and a client-supplied X-Forwarded-For is overwritten;
             * unknown SNI and unknown Host values are refused.

Not covered (cannot be checked from a repository): the real origin certificate and its chain, Cloudflare's
SSL/TLS mode, whether the file on the VPS is populated, firewall rules, or anything about the live server.
No production credentials, VPS, Cloudflare account or Cloudflare dashboard is used. Exit status: 0 all passed,
1 a check failed, 2 the environment cannot run the checks (for example Docker is unavailable): never a silent pass.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import http.client
import ipaddress
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cloudflare_realip as cf  # noqa: E402

REPO = HERE.parent
COMPOSE_FILE = REPO / "docker-compose.prod.yml"
ENV_EXAMPLE = REPO / ".env.production.example"
PROD_CONF = REPO / "nginx" / "prod.conf"
COMMITTED_REALIP = REPO / "nginx" / "cloudflare-realip.conf"
FIXTURE_V4 = HERE / "testdata" / "cloudflare-ips-v4.fixture.txt"
FIXTURE_V6 = HERE / "testdata" / "cloudflare-ips-v6.fixture.txt"

SERVER_NAME = "vedzmani.ir"  # must match server_name in nginx/prod.conf
SPOOF_CF = "203.0.113.7"
SPOOF_XFF = "198.51.100.9"
SPOOF_XRI = "192.0.2.55"

FAILURES: list[str] = []


class EnvironmentUnavailable(RuntimeError):
    pass


def report(ok: bool, name: str, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"\n      {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)
    return ok


def run(cmd, *, env=None, timeout=240):
    return subprocess.run([str(part) for part in cmd], capture_output=True, text=True, timeout=timeout, env=env)


def require_docker() -> None:
    try:
        result = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise EnvironmentUnavailable(f"docker is not usable: {error}") from None
    if result.returncode != 0:
        raise EnvironmentUnavailable("docker daemon is not reachable: " + result.stderr.strip()[:300])


# ----------------------------------------------------------------------------------------------------- compose

def required_compose_variables() -> list[str]:
    return sorted(set(re.findall(r"\$\{([A-Z0-9_]+):\?", COMPOSE_FILE.read_text(encoding="utf-8"))))


def env_text_from_example() -> str:
    lines = []
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if value.startswith("<"):  # placeholder such as <commit-sha>: replace with a harmless dummy
            value = "ci-validation-placeholder-0123456789abcdef"
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def check_compose() -> None:
    print("== docker compose config (docker-compose.prod.yml)")
    required = required_compose_variables()
    with tempfile.TemporaryDirectory(prefix="vedzmani-compose-") as tmp:
        env_file = Path(tmp) / "validation.env"
        env_file.write_text(env_text_from_example(), encoding="utf-8")
        result = run(["docker", "compose", "--env-file", env_file, "-f", COMPOSE_FILE, "config", "-q"])
        report(result.returncode == 0, "compose config -q succeeds with values derived from .env.production.example",
               result.stderr.strip()[:600])

        empty_env = Path(tmp) / "empty.env"
        empty_env.write_text("", encoding="utf-8")
        scrubbed = {key: value for key, value in os.environ.items() if key not in required}
        result = run(["docker", "compose", "--env-file", empty_env, "-f", COMPOSE_FILE, "config", "-q"], env=scrubbed)
        report(result.returncode != 0 and "set " in result.stderr,
               "compose config -q fails fast when required variables are missing",
               f"exit={result.returncode} stderr={result.stderr.strip()[:300]}")
    report(len(required) >= 8, f"compose declares required variables ({len(required)} found)")


# ------------------------------------------------------------------------------------------------------ nginx

def nginx_image() -> str:
    match = re.search(r"^\s+image:\s*(nginx:\S+)\s*$", COMPOSE_FILE.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise EnvironmentUnavailable("cannot find the nginx image tag in docker-compose.prod.yml")
    return match.group(1)


def openssl_binary() -> str:
    found = shutil.which("openssl")
    candidates = [found] if found else []
    candidates += [r"C:\Program Files\Git\usr\bin\openssl.exe", r"C:\Program Files\Git\mingw64\bin\openssl.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise EnvironmentUnavailable("openssl is required to create the throwaway test certificate")


def make_test_certificate(directory: Path) -> None:
    """Self-signed, 2-day certificate for the test only. Created in a temp directory; never stored or committed."""
    result = run([openssl_binary(), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                  "-keyout", directory / "origin.key", "-out", directory / "origin.pem", "-subj", f"/CN={SERVER_NAME}"],
                 timeout=120)
    if result.returncode != 0:
        raise EnvironmentUnavailable("could not create the test certificate: " + result.stderr.strip()[:300])


def mount(source: Path, target: str) -> list[str]:
    return ["--mount", f"type=bind,source={source},target={target},readonly"]


def nginx_test(image: str, realip: Path, certs: Path) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm", "--add-host", "backend:127.0.0.1", "--add-host", "frontend:127.0.0.1",
           *mount(PROD_CONF, "/etc/nginx/conf.d/default.conf"), *mount(realip, "/etc/nginx/cloudflare-realip.conf"),
           *mount(certs, "/etc/nginx/certs"), image, "nginx", "-t"]
    return run(cmd)


ECHO_CONF = """\
server {
    listen 8000;
    listen 3000;
    location / {
        default_type text/plain;
        return 200 "xff=$http_x_forwarded_for;xri=$http_x_real_ip;proto=$http_x_forwarded_proto\\n";
    }
}
"""


def https_get(port: int, *, sni: str, host: str, headers: dict[str, str]) -> tuple[int, str]:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # the test certificate is self-signed on purpose
    raw = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        tls = context.wrap_socket(raw, server_hostname=sni)
    except BaseException:
        raw.close()
        raise
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.sock = tls
    try:
        connection.request("GET", "/", headers={"Host": host, **headers})
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8", "replace")
    finally:
        connection.close()


def parse_echo(body: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in body.strip().split(";") if "=" in part)


class EdgeContainer:
    """One throwaway nginx container running nginx/prod.conf, published on 127.0.0.1 only."""

    def __init__(self, image, network, name, realip: Path, certs: Path):
        self.name = name
        cmd = ["docker", "run", "-d", "--name", name, "--network", network, "-p", "127.0.0.1::443",
               *mount(PROD_CONF, "/etc/nginx/conf.d/default.conf"), *mount(realip, "/etc/nginx/cloudflare-realip.conf"),
               *mount(certs, "/etc/nginx/certs"), image]
        result = run(cmd)
        if result.returncode != 0:
            raise EnvironmentUnavailable("could not start the nginx test container: " + result.stderr.strip()[:400])
        port = run(["docker", "port", name, "443/tcp"]).stdout.strip().splitlines()
        self.port = int(port[0].rsplit(":", 1)[1])
        deadline = time.monotonic() + 30
        while True:
            try:
                https_get(self.port, sni=SERVER_NAME, host=SERVER_NAME, headers={})
                return
            except (OSError, http.client.HTTPException):
                if time.monotonic() > deadline:
                    logs = run(["docker", "logs", name]).stderr[-600:]
                    raise EnvironmentUnavailable("test nginx did not become ready. " + logs) from None
                time.sleep(0.5)

    def get(self, *, host=SERVER_NAME, sni=SERVER_NAME, headers=None):
        return https_get(self.port, sni=sni, host=host, headers=headers or {})


def check_nginx() -> None:
    print("== nginx (isolated test setup)")
    image = nginx_image()
    prefix = f"vedzmani-ci-{uuid.uuid4().hex[:8]}"
    network = f"{prefix}-net"
    created_containers: list[str] = []
    created_network = False
    with tempfile.TemporaryDirectory(prefix="vedzmani-nginx-") as tmp:
        tmp_path = Path(tmp)
        certs = tmp_path / "certs"
        certs.mkdir()
        make_test_certificate(certs)

        generated = tmp_path / "cloudflare-realip.generated.conf"
        code = cf.main(["generate", "--v4-file", str(FIXTURE_V4), "--v6-file", str(FIXTURE_V6),
                        "--generated-on", dt.date.today().isoformat(), "--output", str(generated)])
        report(code == 0 and cf.check_text(generated.read_text(encoding="utf-8"), require_populated=True).ok,
               "generator produces a valid include from the offline fixture lists")

        broken = tmp_path / "broken.conf"
        broken.write_text("set_real_ip_form 192.0.2.0/24;\n", encoding="utf-8")  # typo on purpose: unknown directive

        for label, path, expect_ok in (
            ("committed nginx/cloudflare-realip.conf", COMMITTED_REALIP, True),
            ("generated include (fixture ranges)", generated, True),
            ("deliberately broken include", broken, False),
        ):
            result = nginx_test(image, path, certs)
            output = result.stderr + result.stdout
            if expect_ok:
                report(result.returncode == 0 and "test is successful" in output,
                       f"nginx -t passes with {label}", output.strip()[-500:])
            else:
                report(result.returncode != 0 and "unknown directive" in output,
                       f"nginx -t rejects {label} (proves the include is read)", output.strip()[-500:])

        # --- behaviour through a real proxy hop ------------------------------------------------------------
        try:
            if not report(run(["docker", "network", "create", network]).returncode == 0, "created throwaway network"):
                return
            created_network = True
            echo_conf = tmp_path / "echo.conf"
            echo_conf.write_text(ECHO_CONF, encoding="utf-8")
            echo = f"{prefix}-upstream"
            result = run(["docker", "run", "-d", "--name", echo, "--network", network, "--network-alias", "backend",
                          "--network-alias", "frontend", *mount(echo_conf, "/etc/nginx/conf.d/default.conf"), image])
            if result.returncode != 0:
                raise EnvironmentUnavailable("could not start the echo upstream: " + result.stderr.strip()[:300])
            created_containers.append(echo)

            # Phase A: the peer (this test client, as Docker presents it) is NOT in the trusted ranges.
            edge_a = f"{prefix}-edge-untrusted"
            created_containers.append(edge_a)
            edge = EdgeContainer(image, network, edge_a, generated, certs)
            status, body = edge.get(headers={"CF-Connecting-IP": SPOOF_CF, "X-Forwarded-For": SPOOF_XFF, "X-Real-IP": SPOOF_XRI})
            seen = parse_echo(body)
            peer = seen.get("xri", "")
            try:
                ipaddress.ip_address(peer)
                peer_ok = True
            except ValueError:
                peer_ok = False
            report(status == 200 and peer_ok and seen.get("xff") == peer and peer not in {SPOOF_CF, SPOOF_XFF, SPOOF_XRI},
                   "untrusted peer: spoofed CF-Connecting-IP / X-Forwarded-For / X-Real-IP are ignored",
                   f"status={status} echo={body.strip()}")
            report(seen.get("proto") == "https", "X-Forwarded-Proto is https behind the TLS-terminating Nginx", body.strip())

            status, body = edge.get(host="evil.example")
            report(status in (404, 421) and "xff=" not in body,
                   "a Host that is not a configured server name is not proxied (404 or 421)",
                   f"status={status} body={body.strip()[:200]}")
            try:
                edge.get(sni="other.example")
                refused = False
            except (ssl.SSLError, ConnectionResetError, ConnectionAbortedError):
                refused = True
            report(refused, "TLS handshake with an unknown SNI name is refused")
            run(["docker", "rm", "-f", edge_a])
            created_containers.remove(edge_a)

            # Phase B: trust exactly the peer address seen above, using the generator's own renderer.
            if not peer_ok:
                return
            trusted = tmp_path / "trust-test-peer.conf"
            trusted.write_text(cf.render([ipaddress.ip_network(peer)], [], generated_on=dt.date.today()), encoding="utf-8")
            edge_b = f"{prefix}-edge-trusted"
            created_containers.append(edge_b)
            edge = EdgeContainer(image, network, edge_b, trusted, certs)
            status, body = edge.get(headers={"CF-Connecting-IP": SPOOF_CF, "X-Forwarded-For": SPOOF_XFF, "X-Real-IP": SPOOF_XRI})
            seen = parse_echo(body)
            report(status == 200 and seen.get("xff") == SPOOF_CF and seen.get("xri") == SPOOF_CF,
                   "trusted peer: CF-Connecting-IP becomes the client address and replaces a client X-Forwarded-For",
                   f"status={status} echo={body.strip()}")
            status, body = edge.get(headers={"X-Forwarded-For": SPOOF_XFF, "X-Real-IP": SPOOF_XRI})
            seen = parse_echo(body)
            report(status == 200 and seen.get("xff") == peer and seen.get("xri") == peer,
                   "trusted peer without CF-Connecting-IP: the peer address is used, client X-Forwarded-For is dropped",
                   f"status={status} echo={body.strip()}")
            status, body = edge.get(headers={"CF-Connecting-IP": "not-an-address"})
            seen = parse_echo(body)
            report(status == 200 and seen.get("xff") == peer,
                   "trusted peer with a malformed CF-Connecting-IP: ignored, peer address is used",
                   f"status={status} echo={body.strip()}")
        finally:
            for name in created_containers:
                run(["docker", "rm", "-f", name])
            if created_network:
                run(["docker", "network", "rm", network])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate the production Compose and Nginx files in a throwaway setup.")
    parser.add_argument("--only", choices=["compose", "nginx"], help="run one group (default: both)")
    args = parser.parse_args(argv)
    try:
        require_docker()
        if args.only in (None, "compose"):
            check_compose()
        if args.only in (None, "nginx"):
            check_nginx()
    except EnvironmentUnavailable as error:
        print(f"ERROR: cannot run the checks: {error}", file=sys.stderr)
        return 2
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
