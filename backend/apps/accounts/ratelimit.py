"""Cache-backed (Redis in dev/prod) fixed-window rate limiting.

Keys: ``rl:<scope>:<identifier>`` (phone identifiers are hashed, so no raw
phone numbers sit in Redis). Every key has a TTL equal to its window.
Counters are advisory abuse controls only; the authoritative brute-force
limit (attempt_count) lives on the OTPChallenge row in PostgreSQL.

If the cache is unavailable the exception propagates: auth fails closed
rather than silently dropping its abuse protection.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache

from .exceptions import RateLimited


def get_client_ip(request) -> str:
    """Client IP. X-Forwarded-For is trusted ONLY when AUTH_TRUSTED_PROXY_COUNT
    says how many proxies we sit behind; otherwise it is ignored (spoofable)."""
    hops = settings.AUTH_TRUSTED_PROXY_COUNT
    if hops > 0:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.META.get("REMOTE_ADDR", "") or "unknown"


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
