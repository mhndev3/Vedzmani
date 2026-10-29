#!/usr/bin/env python3
"""Generate and validate the Cloudflare real-client-IP include for nginx/prod.conf (standard library only).

Why this exists: Cloudflare's address ranges change, so they are never hardcoded in this repository. The
generated include tells Nginx to take the visitor address from `CF-Connecting-IP`, but ONLY when the TCP
connection itself comes from a published Cloudflare range. From any other peer the header is ignored, so a
client that reaches the origin directly cannot choose its own address.

Commands
    generate  Fetch https://www.cloudflare.com/ips-v4 and /ips-v6 (or read local copies), validate them, and
              write the include atomically. Nothing is written when validation fails.
    check     Validate an existing include. A file with no directives is reported as PLACEHOLDER (real client
              IP restoration is NOT active); use --require-populated to turn that into a failure.

This script never talks to the Cloudflare dashboard or API, needs no credentials, and does not touch Nginx.
Applying the file on a server (and recreating the nginx container) is a separate, owner-approved step; see
docs/PRODUCTION_INFRASTRUCTURE.md, section 4.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import ipaddress
import os
import re
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

IPV4_URL = "https://www.cloudflare.com/ips-v4"
IPV6_URL = "https://www.cloudflare.com/ips-v6"

REAL_IP_HEADER = "CF-Connecting-IP"

# Sanity limits. They fail closed: a response outside them is rejected and a human has to look at it.
MAX_BODY_BYTES = 64 * 1024
MIN_RANGES_V4 = 5  # Cloudflare publishes a few more than a dozen; a short list means a truncated response.
MIN_RANGES_V6 = 3
MIN_PREFIX_V4 = 12  # widest accepted IPv4 range is a /12 (Cloudflare's widest is currently a /13)
MIN_PREFIX_V6 = 24  # widest accepted IPv6 range is a /24 (Cloudflare's widest is currently a /29)

_GENERATED_RE = re.compile(r"^#\s*Generated:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
_SET_FROM_RE = re.compile(r"^set_real_ip_from\s+(\S+);$")
_HEADER_RE = re.compile(r"^real_ip_header\s+(\S+);$")
_RECURSIVE_RE = re.compile(r"^real_ip_recursive\s+(\S+);$")


class RangeError(ValueError):
    """A published range list (or an include file) failed validation."""


def parse_ranges(text: str, version: int, *, source: str = "list"):
    """Parse one address list (one CIDR per line) into validated, sorted, de-duplicated networks."""
    networks = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        networks.append(_validate_network(line, version, where=f"{source} line {number}"))
    if not networks:
        raise RangeError(f"{source}: no ranges found")
    minimum = MIN_RANGES_V4 if version == 4 else MIN_RANGES_V6
    unique = sorted(set(networks), key=lambda n: (int(n.network_address), n.prefixlen))
    if len(unique) < minimum:
        raise RangeError(f"{source}: only {len(unique)} IPv{version} ranges (expected at least {minimum}); refusing a short list")
    return unique


def _validate_network(value: str, version: int, *, where: str):
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        # The offending text is not echoed: it may be an HTML error page or other untrusted content.
        raise RangeError(f"{where}: not a valid CIDR range") from None
    if network.version != version:
        raise RangeError(f"{where}: expected an IPv{version} range, got IPv{network.version}")
    if not network.is_global:
        raise RangeError(f"{where}: {network} is not a publicly routable range (private, loopback, reserved or similar)")
    minimum_prefix = MIN_PREFIX_V4 if version == 4 else MIN_PREFIX_V6
    if network.prefixlen < minimum_prefix:
        raise RangeError(f"{where}: {network} is broader than /{minimum_prefix}; refusing to trust that many addresses")
    return network


def render(v4, v6, *, generated_on: dt.date, sources: tuple[str, str] = (IPV4_URL, IPV6_URL)) -> str:
    """Render the Nginx include. Takes already-validated networks."""
    lines = [
        "# GENERATED FILE. Do not edit by hand; regenerate with scripts/cloudflare_realip.py.",
        f"# Generated: {generated_on.isoformat()}",
        f"# Sources: {sources[0]} and {sources[1]}",
        "# Nginx takes the client address from the header below only when the TCP peer is inside one of these",
        "# ranges. Any other peer is not trusted and its CF-Connecting-IP / X-Forwarded-For are ignored.",
    ]
    lines += [f"set_real_ip_from {network};" for network in (*v4, *v6)]
    lines += [f"real_ip_header {REAL_IP_HEADER};", "real_ip_recursive off;", ""]
    return "\n".join(lines)


def fetch(url: str, *, timeout: float = 15.0) -> str:
    """Download one list over HTTPS with certificate verification, a size cap and a status check."""
    if not url.startswith("https://"):
        raise RangeError(f"{url}: only https:// sources are accepted")
    request = urllib.request.Request(url, headers={"User-Agent": "vedzmani-cloudflare-realip/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (scheme checked above)
        if response.status != 200:
            raise RangeError(f"{url}: HTTP {response.status}")
        body = response.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise RangeError(f"{url}: response larger than {MAX_BODY_BYTES} bytes")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise RangeError(f"{url}: response is not UTF-8 text") from None


def write_atomic(path: Path, content: str) -> None:
    """Write next to the target and rename, so a reader never sees a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


@dataclass
class CheckResult:
    status: str  # "populated" or "placeholder"
    ranges: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    generated_on: dt.date | None = None

    @property
    def ok(self) -> bool:
        return not self.problems


def check_text(text: str, *, require_populated: bool = False, max_age_days: int | None = None,
               today: dt.date | None = None) -> CheckResult:
    """Validate an include. Only the three directives this feature needs are accepted."""
    problems: list[str] = []
    ranges = []
    headers: list[str] = []
    recursive: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = _SET_FROM_RE.match(line)
        if match:
            version = 6 if ":" in match.group(1) else 4
            try:
                ranges.append(_validate_network(match.group(1), version, where=f"line {number}"))
            except RangeError as error:
                problems.append(str(error))
            continue
        match = _HEADER_RE.match(line)
        if match:
            headers.append(match.group(1))
            continue
        match = _RECURSIVE_RE.match(line)
        if match:
            recursive.append(match.group(1))
            continue
        problems.append(
            f"line {number}: unexpected directive (only set_real_ip_from, real_ip_header and real_ip_recursive are allowed)"
        )

    generated = _GENERATED_RE.search(text)
    generated_on = dt.date.fromisoformat(generated.group(1)) if generated else None

    if not ranges and not headers and not recursive and not problems:
        result = CheckResult(status="placeholder", generated_on=generated_on)
        if require_populated:
            result.problems.append("no Cloudflare ranges configured: real client IP restoration is NOT active")
        return result

    if headers != [REAL_IP_HEADER]:
        problems.append(
            f"expected exactly one `real_ip_header {REAL_IP_HEADER};` "
            "(Nginx's default header is X-Real-IP, which a client can send)"
        )
    if recursive != ["off"]:
        problems.append("expected exactly one `real_ip_recursive off;`")
    unique = set(ranges)
    v4 = [n for n in unique if n.version == 4]
    v6 = [n for n in unique if n.version == 6]
    if len(v4) < MIN_RANGES_V4:
        problems.append(f"only {len(v4)} IPv4 ranges (expected at least {MIN_RANGES_V4})")
    if len(v6) < MIN_RANGES_V6:
        problems.append(f"only {len(v6)} IPv6 ranges (expected at least {MIN_RANGES_V6})")
    if len(unique) != len(ranges):
        problems.append("duplicate set_real_ip_from ranges")

    if max_age_days is not None:
        today = today or dt.date.today()
        if generated_on is None:
            problems.append("no `# Generated: YYYY-MM-DD` line, so the age of the ranges cannot be checked")
        elif (today - generated_on).days > max_age_days:
            problems.append(f"ranges were generated {(today - generated_on).days} days ago (limit {max_age_days}); regenerate")

    ordered = sorted(unique, key=lambda n: (n.version, int(n.network_address), n.prefixlen))
    return CheckResult(status="populated", ranges=ordered, problems=problems, generated_on=generated_on)


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        v4_text = Path(args.v4_file).read_text(encoding="utf-8") if args.v4_file else fetch(IPV4_URL)
        v6_text = Path(args.v6_file).read_text(encoding="utf-8") if args.v6_file else fetch(IPV6_URL)
        v4 = parse_ranges(v4_text, 4, source="ips-v4")
        v6 = parse_ranges(v6_text, 6, source="ips-v6")
    except (RangeError, OSError) as error:
        print(f"ERROR: {error}\nNothing was written.", file=sys.stderr)
        return 1
    generated_on = dt.date.fromisoformat(args.generated_on) if args.generated_on else dt.datetime.now(dt.timezone.utc).date()
    content = render(v4, v6, generated_on=generated_on)
    result = check_text(content)  # defence in depth: the rendered file must pass its own validation
    if not result.ok:
        print("ERROR: rendered file failed validation: " + "; ".join(result.problems), file=sys.stderr)
        return 1
    if args.stdout:
        sys.stdout.write(content)
    else:
        write_atomic(Path(args.output), content)
        print(f"Wrote {len(v4)} IPv4 and {len(v6)} IPv6 ranges to {args.output}")
        print("Next (owner-approved, on the server): run nginx -t, then recreate the nginx container. See docs section 4.")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        text = Path(args.path).read_text(encoding="utf-8")
    except OSError as error:
        print(f"ERROR: cannot read {args.path}: {error}", file=sys.stderr)
        return 2
    result = check_text(text, require_populated=args.require_populated, max_age_days=args.max_age_days)
    if result.status == "placeholder":
        print(f"PLACEHOLDER: {args.path} contains no directives. Real client IP restoration is NOT active.")
    else:
        v4 = sum(1 for n in result.ranges if n.version == 4)
        print(f"POPULATED: {args.path}: {v4} IPv4 and {len(result.ranges) - v4} IPv6 ranges, generated {result.generated_on or 'unknown'}")
    for problem in result.problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate the Cloudflare real-IP include for nginx/prod.conf.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="fetch, validate and write the include")
    target = gen.add_mutually_exclusive_group(required=True)
    target.add_argument("--output", help="file to write (atomic replace)")
    target.add_argument("--stdout", action="store_true", help="print instead of writing a file")
    gen.add_argument("--v4-file", help="read IPv4 ranges from this file instead of downloading (offline/tests)")
    gen.add_argument("--v6-file", help="read IPv6 ranges from this file instead of downloading (offline/tests)")
    gen.add_argument("--generated-on", help="override the date stamp, YYYY-MM-DD (tests)")
    gen.set_defaults(func=_cmd_generate)

    chk = sub.add_parser("check", help="validate an existing include")
    chk.add_argument("path")
    chk.add_argument("--require-populated", action="store_true", help="fail when the file has no ranges")
    chk.add_argument("--max-age-days", type=int, help="fail when the `# Generated:` date is older than this")
    chk.set_defaults(func=_cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
