"""Purge of expired sessions / OTP challenges (apps/accounts/cleanup.py, `purge_expired_auth_data`).

Everything runs against the isolated test database; no production access, no real delivery."""

import threading
import time
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts import cleanup, services
from apps.accounts.delivery import InMemoryDelivery
from apps.accounts.models import OTPChallenge

pytestmark = pytest.mark.django_db

PHONE = "+989123456789"
RETENTION = timedelta(days=30)


def ago(**kw):
    return timezone.now() - timedelta(**kw)


def later(**kw):
    return timezone.now() + timedelta(**kw)


def make_session(key, expire_date):
    return Session.objects.create(session_key=key, session_data="e30:x:y", expire_date=expire_date)


def make_challenge(*, expires_at, consumed_at=None, phone=PHONE):
    return OTPChallenge.objects.create(
        phone=phone, purpose="login", code_hash="0" * 64, salt="s" * 32, expires_at=expires_at, consumed_at=consumed_at
    )


def run(*args):
    out = StringIO()
    call_command("purge_expired_auth_data", *args, stdout=out)
    return out.getvalue()


# --------------------------------------------------------------- sessions --
def test_expired_sessions_are_eligible_and_live_ones_stay():
    make_session("expired-1h", ago(hours=1))
    make_session("expired-1s", ago(seconds=1))
    make_session("browser-session-live", later(days=10))  # non-remember login: server row still valid
    make_session("remember-live", later(days=29))
    assert cleanup.purge_expired_sessions(dry_run=False) == 2
    assert set(Session.objects.values_list("session_key", flat=True)) == {"browser-session-live", "remember-live"}


def test_session_purge_is_idempotent():
    make_session("a", ago(days=3))
    assert cleanup.purge_expired_sessions(dry_run=False) == 1
    assert cleanup.purge_expired_sessions(dry_run=False) == 0
    assert cleanup.purge_expired_sessions(dry_run=False) == 0


def test_an_active_login_survives_the_purge(api):
    api.login(PHONE.replace("+98", "0"))
    make_session("stale", ago(days=1))
    cleanup.purge_expired_sessions(dry_run=False)
    assert not Session.objects.filter(session_key="stale").exists()
    assert api.get("/api/auth/me/").status_code == 200


# ------------------------------------------------------------ OTP matrix --
def test_otp_eligibility_follows_the_single_retention_rule():
    keep = {
        "valid-now": make_challenge(expires_at=later(minutes=3)),
        "consumed-but-not-yet-expired": make_challenge(expires_at=later(minutes=2), consumed_at=ago(minutes=3)),
        "expired-2-days-ago": make_challenge(expires_at=ago(days=2)),
        "expired-29-days-ago": make_challenge(expires_at=ago(days=29)),
    }
    drop = {
        "expired-unused-40d": make_challenge(expires_at=ago(days=40)),
        "consumed-40d": make_challenge(expires_at=ago(days=40), consumed_at=ago(days=40, minutes=2)),
        "invalidated-after-failed-delivery-40d": make_challenge(expires_at=ago(days=40)),
    }
    assert cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False) == len(drop)
    remaining = set(OTPChallenge.objects.values_list("pk", flat=True))
    assert remaining == {c.pk for c in keep.values()}
    assert not remaining & {c.pk for c in drop.values()}


def test_otp_purge_is_idempotent():
    make_challenge(expires_at=ago(days=45))
    assert cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False) == 1
    assert cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False) == 0


def test_retention_below_one_day_is_rejected():
    for bad in (timedelta(0), timedelta(hours=23)):
        with pytest.raises(ValueError):
            cleanup.purge_expired_otp_challenges(retention=bad, dry_run=False)


# ------------------------------------------- security properties after purge --
def test_a_purged_consumed_code_can_never_be_replayed(api):
    api.request_otp()
    code = api.last_code()
    assert api.verify(code).status_code == 200  # consumes it
    api.post("/api/auth/logout/")
    OTPChallenge.objects.update(expires_at=ago(days=45))
    assert cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False) == 1
    replay = api.verify(code)
    assert replay.status_code == 400 and replay.json()["error"]["code"] == "otp_invalid"
    assert api.get("/api/auth/me/").status_code == 401


def test_a_valid_code_in_flight_survives_the_purge(api):
    api.request_otp()
    make_challenge(expires_at=ago(days=60), phone="+989129999999")
    assert cleanup.purge_expired_otp_challenges(retention=timedelta(days=1), dry_run=False) == 1
    assert api.verify(api.last_code()).status_code == 200


def test_purging_expired_rows_never_reopens_a_guess_window(api, settings):
    """attempt_count lives on the row, but only EXPIRED rows are deleted, and an expired row cannot be guessed against."""
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    api.request_otp()
    bad = "000000" if api.last_code() != "000000" else "000001"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        api.verify(bad)
    OTPChallenge.objects.update(expires_at=ago(days=45))
    cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False)
    assert not OTPChallenge.objects.exists()
    assert api.verify(api.last_code()).json()["error"]["code"] == "otp_invalid"  # the old (right) code is useless


# ------------------------------------------------------- bounds / batching --
def test_batching_drains_everything_and_max_batches_bounds_one_run():
    for i in range(5):
        make_session(f"s{i}", ago(days=1 + i))
    assert cleanup.purge_expired_sessions(dry_run=False, batch_size=2, max_batches=1) == 2  # one bounded run
    assert Session.objects.count() == 3
    assert cleanup.purge_expired_sessions(dry_run=False, batch_size=2, max_batches=10) == 3  # a later run drains
    assert Session.objects.count() == 0


def test_invalid_bounds_are_rejected():
    with pytest.raises(ValueError):
        cleanup.purge_expired_sessions(dry_run=False, batch_size=0)
    with pytest.raises(ValueError):
        cleanup.purge_expired_sessions(dry_run=False, max_batches=0)


# --------------------------------------------------------------- command --
def test_command_defaults_to_dry_run_and_deletes_nothing():
    make_session("old", ago(days=2))
    make_challenge(expires_at=ago(days=60))
    output = run("--otp-retention-days", "30")
    assert "DRY RUN" in output and "would delete 1 expired row" in output and "Nothing was deleted" in output
    assert Session.objects.count() == 1 and OTPChallenge.objects.count() == 1


def test_command_skips_otp_rows_unless_retention_is_given():
    make_session("old", ago(days=2))
    make_challenge(expires_at=ago(days=400))
    output = run("--execute")
    assert "sessions: deleted 1" in output and "otp_challenges: skipped" in output
    assert not Session.objects.exists() and OTPChallenge.objects.count() == 1  # no policy -> OTP rows untouched


def test_command_execute_with_retention_and_idempotent_rerun():
    make_session("old", ago(days=2))
    make_challenge(expires_at=ago(days=60))
    make_challenge(expires_at=ago(days=5))
    first = run("--execute", "--otp-retention-days", "30")
    assert "sessions: deleted 1" in first and "otp_challenges: deleted 1 row" in first
    second = run("--execute", "--otp-retention-days", "30")
    assert "sessions: deleted 0" in second and "otp_challenges: deleted 0 row" in second
    assert OTPChallenge.objects.count() == 1  # the one inside the retention window


@pytest.mark.parametrize("args", [["--otp-retention-days", "0"], ["--batch-size", "0"], ["--max-batches", "0"]])
def test_command_rejects_unsafe_arguments(args):
    with pytest.raises(CommandError):
        run("--execute", *args)


def test_command_output_never_contains_phone_numbers_or_keys():
    make_session("SECRET-SESSION-KEY-123", ago(days=2))
    make_challenge(expires_at=ago(days=60))
    output = run("--execute", "--otp-retention-days", "30")
    assert "SECRET-SESSION-KEY" not in output and "989123456789" not in output


# ------------------------------------------------------------ concurrency --
def _hold_lock(model, pk, locked: threading.Event, release: threading.Event):
    try:
        with transaction.atomic():
            model.objects.select_for_update().get(pk=pk)
            locked.set()
            release.wait(timeout=20)
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["otp", "session"])
def test_purge_skips_a_locked_row_without_waiting_and_picks_it_up_next_run(kind):
    if kind == "otp":
        row, model = make_challenge(expires_at=ago(days=60)), OTPChallenge
        purge = lambda: cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False)  # noqa: E731
    else:
        row, model = make_session("locked", ago(days=2)), Session
        purge = lambda: cleanup.purge_expired_sessions(dry_run=False)  # noqa: E731
    locked, release = threading.Event(), threading.Event()
    holder = threading.Thread(target=_hold_lock, args=(model, row.pk, locked, release))
    holder.start()
    try:
        assert locked.wait(timeout=10)
        started = time.monotonic()
        deleted_while_locked = purge()
        elapsed = time.monotonic() - started
    finally:
        release.set()
        holder.join(timeout=20)
    assert deleted_while_locked == 0 and elapsed < 5  # skipped, did not block on the lock
    assert model.objects.filter(pk=row.pk).exists()
    assert purge() == 1  # lock released: the next run removes it


@pytest.mark.django_db(transaction=True)
def test_concurrent_purges_and_verification_never_lose_or_reuse_a_valid_code():
    services.request_otp(phone=PHONE, purpose="login", ip="203.0.113.9")
    code = InMemoryDelivery.outbox[-1]["code"]
    for i in range(30):
        make_challenge(expires_at=ago(days=60), phone=f"+98912000{i:04d}")
    stop, errors = threading.Event(), []

    def purger():
        try:
            while not stop.is_set():
                cleanup.purge_expired_otp_challenges(retention=RETENTION, dry_run=False, batch_size=5)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=purger) for _ in range(3)]
    for t in threads:
        t.start()
    try:
        user, created = services.verify_otp(phone=PHONE, purpose="login", code=code, ip="203.0.113.9")
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=20)
    assert not errors and created and user.phone == PHONE
    challenge = OTPChallenge.objects.get(phone=PHONE)  # the valid challenge was never deleted
    assert challenge.consumed_at is not None
    assert OTPChallenge.objects.exclude(phone=PHONE).count() == 0  # all the old ones were purged
