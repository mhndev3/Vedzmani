"""Cache-backed (Redis in dev/prod) fixed-window rate limiting.

Keys: ``rl:<scope>:<identifier>`` (phone identifiers are hashed, so no raw
phone numbers sit in Redis). Every key has a TTL equal to its window.
Counters are advisory abuse controls only; the authoritative brute-force
limit (attempt_count) lives on the OTPChallenge row in PostgreSQL.

If the cache is unavailable the exception propagates: auth fails closed
rather than silently dropping its abuse protection.
"""

import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache

from .exceptions import RateLimited


def _canonical_ip(value: str) -> str | None:
    """Rate-limit identity for an address, or None when `value` is not an IP address at all.

    IPv4 is used as is. IPv4-mapped IPv6 collapses to its IPv4. Any other IPv6 address collapses to its /64:
    one subscriber normally controls a whole /64, so per-address buckets would let a single client mint
    unlimited fresh identities. Anything that is not an IP never becomes a rate-limit key."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if address.version == 6:
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network((address, 64), strict=False))
    return str(address)


def get_client_ip(request) -> str:
    """Client IP. X-Forwarded-For is trusted ONLY when AUTH_TRUSTED_PROXY_COUNT
    says how many proxies we sit behind; otherwise it is ignored (spoofable).
    The trusted entry must be a valid IP, otherwise the peer address is used (coarse but never attacker-chosen
    text). Safe only while the backend is reachable exclusively through the trusted proxy (see AUTH.md)."""
    hops = settings.AUTH_TRUSTED_PROXY_COUNT
    if hops > 0:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            candidate = _canonical_ip(forwarded[-hops])
            if candidate:
                return candidate
    return _canonical_ip(request.META.get("REMOTE_ADDR", "")) or "unknown"


def _ident(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def _within_limit(scope: str, ident: str, limit: int, window: int) -> bool:
    key = f"rl:{scope}:{ident}"
    if cache.add(key, 1, timeout=window):
        return True
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add() and incr()
        cache.set(key, 1, timeout=window)
        count = 1
    return count <= limit


def enforce_otp_request(ip: str, phone: str) -> None:
    s = settings
    if not _within_limit("otp_req_ip", _ident(ip), s.OTP_REQUEST_IP_LIMIT, 3600):
        raise RateLimited(wait=3600)
    if not cache.add(f"rl:otp_req_cooldown:{_ident(phone)}", 1, timeout=s.OTP_REQUEST_COOLDOWN_SECONDS):
        raise RateLimited(wait=s.OTP_REQUEST_COOLDOWN_SECONDS)
    if not _within_limit("otp_req_phone", _ident(phone), s.OTP_REQUEST_PHONE_LIMIT, 3600):
        raise RateLimited(wait=3600)


def enforce_otp_verify(ip: str) -> None:
    s = settings
    if not _within_limit("otp_verify_ip", _ident(ip), s.OTP_VERIFY_IP_LIMIT, s.OTP_VERIFY_IP_WINDOW_SECONDS):
        raise RateLimited(wait=s.OTP_VERIFY_IP_WINDOW_SECONDS)
