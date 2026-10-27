"""Bounded, idempotent purge of expired authentication data.

Nothing in the repo schedules this (see AUTH.md): it is an explicit operation, safe to run by hand or from any
scheduler the owner chooses. Eligibility rules (the only rows ever deleted):

* ``django_session``: ``expire_date < now``. Django's session store already refuses such rows, so deleting them
  changes nothing for any user and they carry no audit data.
* ``OTPChallenge``: ``expires_at < now - retention``. Consumed, invalidated (delivery failed) and simply unused
  challenges all follow this one rule, because each of them is expired by then. A challenge that is still valid,
  or expired less than ``retention`` ago, is never touched. ``retention`` has NO default: it is an owner policy
  (the rows hold phone numbers, attempt counts and timestamps that may serve abuse investigation).

Deleting an expired row can never reopen a guessing window or allow a code to be reused: an expired challenge
is rejected by ``verify_otp`` anyway. The only visible effect is that a *very* old code answers ``otp_invalid``
instead of ``otp_expired``/``otp_consumed``.

Concurrency: rows are picked with ``FOR UPDATE SKIP LOCKED`` in small batches, so the purge never waits for, and
never deletes, a row that ``verify_otp`` currently holds locked; it just leaves it for the next run.
"""

from datetime import datetime, timedelta

from django.contrib.sessions.models import Session
from django.db import models, transaction
from django.utils import timezone

from .models import OTPChallenge

DEFAULT_BATCH_SIZE = 1000
DEFAULT_MAX_BATCHES = 100  # bounds one run (default 100k rows); repeated runs drain any backlog


def expired_sessions(now: datetime) -> models.QuerySet:
    return Session.objects.filter(expire_date__lt=now)


def expired_otp_challenges(now: datetime, retention: timedelta) -> models.QuerySet:
    return OTPChallenge.objects.filter(expires_at__lt=now - retention)


def _delete_in_batches(queryset: models.QuerySet, *, batch_size: int, max_batches: int) -> int:
    if batch_size < 1 or max_batches < 1:
        raise ValueError("batch_size and max_batches must be >= 1")
    model = queryset.model
    deleted = 0
    for _ in range(max_batches):
        with transaction.atomic():
            pks = list(queryset.select_for_update(skip_locked=True).values_list("pk", flat=True)[:batch_size])
            if not pks:
                break
            count, _per_model = model._default_manager.filter(pk__in=pks).delete()
        deleted += count
        if len(pks) < batch_size:
            break
    return deleted


def purge_expired_sessions(
    *, now: datetime | None = None, dry_run: bool = True, batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_BATCHES,
) -> int:
    """Return the number of rows deleted (dry run: the number that WOULD be eligible)."""
    queryset = expired_sessions(now or timezone.now())
    if dry_run:
        return queryset.count()
    return _delete_in_batches(queryset, batch_size=batch_size, max_batches=max_batches)


def purge_expired_otp_challenges(
    *, retention: timedelta, now: datetime | None = None, dry_run: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE, max_batches: int = DEFAULT_MAX_BATCHES,
) -> int:
    """Return the number of rows deleted (dry run: the number that WOULD be eligible)."""
    if retention < timedelta(days=1):
        raise ValueError("OTP retention must be at least 1 day")
    queryset = expired_otp_challenges(now or timezone.now(), retention)
    if dry_run:
        return queryset.count()
    return _delete_in_batches(queryset, batch_size=batch_size, max_batches=max_batches)
