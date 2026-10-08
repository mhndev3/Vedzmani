"""OTP request / verify business logic (the only place it lives)."""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import ratelimit
from .delivery import OTPDeliveryError, get_delivery
from .exceptions import (
    AccountDisabled,
    DeliveryUnavailable,
    OTPAttemptsExceeded,
    OTPConsumed,
    OTPExpired,
    OTPInvalid,
)
from .models import OTPChallenge, User

logger = logging.getLogger(__name__)

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CODE_LENGTH = 6


def normalize_code(raw: str) -> str:
    return raw.translate(_DIGITS).strip()


def _hash_code(*, code: str, salt: str, phone: str, purpose: str) -> str:
    """HMAC keyed with SECRET_KEY: a leaked DB alone cannot brute-force the
    6-digit space offline, and hashes are bound to phone + purpose + salt."""
    message = f"{salt}:{phone}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def request_otp(*, phone: str, purpose: str, ip: str) -> None:
    """Issue and deliver a code. Never reveals whether the phone has an
    account (the User table is not touched here at all)."""
    ratelimit.enforce_otp_request(ip, phone)

    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    salt = secrets.token_hex(8)
    now = timezone.now()
    with transaction.atomic():
        # Only the newest code is ever valid.
        OTPChallenge.objects.filter(
            phone=phone, purpose=purpose, consumed_at__isnull=True, expires_at__gt=now
        ).update(expires_at=now)
        challenge = OTPChallenge.objects.create(
            phone=phone,
            purpose=purpose,
            salt=salt,
            code_hash=_hash_code(code=code, salt=salt, phone=phone, purpose=purpose),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )

    try:
        get_delivery().send(phone=phone, code=code, purpose=purpose)
    except OTPDeliveryError:
        logger.error("OTP delivery failed (challenge=%s)", challenge.pk)
        OTPChallenge.objects.filter(pk=challenge.pk).update(expires_at=timezone.now())
        raise DeliveryUnavailable() from None


def verify_otp(*, phone: str, purpose: str, code: str, ip: str) -> tuple[User, bool]:
    """Verify + consume a code and return (user, created). Raises an OTPError.

    The challenge row is locked (SELECT ... FOR UPDATE) so two concurrent
    verifications can never both consume it. Failure bookkeeping (attempt
    counter) is committed before the error is raised.
    """
    ratelimit.enforce_otp_verify(ip)
    code = normalize_code(code)
    now = timezone.now()

    failure: type[Exception] | None = None
    user: User | None = None
    created = False

    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(phone=phone, purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            failure = OTPInvalid
        elif challenge.consumed_at is not None:
            failure = OTPConsumed
        elif challenge.expires_at <= now:
            failure = OTPExpired
        elif challenge.attempt_count >= settings.OTP_MAX_ATTEMPTS:
            failure = OTPAttemptsExceeded
        else:
            expected = _hash_code(code=code, salt=challenge.salt, phone=phone, purpose=purpose)
            if hmac.compare_digest(expected, challenge.code_hash):
                challenge.consumed_at = now
                challenge.save(update_fields=["consumed_at"])
                user, created = User.objects.get_or_create_by_phone(phone)
                if not user.is_active:
                    failure = AccountDisabled
            else:
                challenge.attempt_count += 1
                challenge.save(update_fields=["attempt_count"])
                failure = OTPInvalid

    if failure is not None:
        raise failure()
    assert user is not None
    return user, created
