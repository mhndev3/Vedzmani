"""Purge expired authentication data (expired sessions, expired OTP challenges). See apps/accounts/cleanup.py.

    manage.py purge_expired_auth_data                         # dry run: only reports what would be deleted
    manage.py purge_expired_auth_data --execute               # sessions only
    manage.py purge_expired_auth_data --execute --otp-retention-days 30

OTP challenges are only purged when --otp-retention-days is given: how long they are kept is an owner decision.
Output contains counts only (never phone numbers, codes or session keys).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import cleanup


class Command(BaseCommand):
    help = "Delete expired Django sessions and (optionally) OTP challenges expired longer than the given retention."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Actually delete. Without it nothing is deleted.")
        parser.add_argument(
            "--otp-retention-days",
            type=int,
            default=None,
            help="Delete OTP challenges that expired more than N days ago (N >= 1). Omit to leave OTP rows alone.",
        )
        parser.add_argument("--batch-size", type=int, default=cleanup.DEFAULT_BATCH_SIZE)
        parser.add_argument(
            "--max-batches",
            type=int,
            default=cleanup.DEFAULT_MAX_BATCHES,
            help="Upper bound of batches per table in one run; run again to continue a large backlog.",
        )

    def handle(self, *args, **options):
        dry_run = not options["execute"]
        batch_size, max_batches = options["batch_size"], options["max_batches"]
        retention_days = options["otp_retention_days"]
        if batch_size < 1 or max_batches < 1:
            raise CommandError("--batch-size and --max-batches must be >= 1.")
        if retention_days is not None and retention_days < 1:
            raise CommandError("--otp-retention-days must be >= 1.")

        verb = "would delete" if dry_run else "deleted"
        mode = "DRY RUN" if dry_run else "EXECUTE"
        self.stdout.write(f"[{mode}] purge_expired_auth_data")

        sessions = cleanup.purge_expired_sessions(dry_run=dry_run, batch_size=batch_size, max_batches=max_batches)
        self.stdout.write(f"sessions: {verb} {sessions} expired row(s)")

        if retention_days is None:
            self.stdout.write("otp_challenges: skipped (--otp-retention-days not given; retention is an owner decision)")
        else:
            otp = cleanup.purge_expired_otp_challenges(
                retention=timedelta(days=retention_days), dry_run=dry_run, batch_size=batch_size, max_batches=max_batches
            )
            self.stdout.write(f"otp_challenges: {verb} {otp} row(s) expired more than {retention_days} day(s) ago")

        if dry_run:
            self.stdout.write("Nothing was deleted. Re-run with --execute to delete.")
