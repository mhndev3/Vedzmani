"""User + OTP challenge models.

PostgreSQL is the source of truth for both. Redis is only used for
rate-limit counters (see ratelimit.py), never for authentication state.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from .phone import CANONICAL_RE, normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, phone: str, password: str | None, **extra):
        user = self.model(phone=normalize_phone(phone), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # customers authenticate by OTP only
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not password:
            raise ValueError("Superuser requires a password (admin login).")
        return self._create(phone, password, **extra)

    def get_or_create_by_phone(self, phone: str):
        """Race-safe get-or-create. The UNIQUE constraint is the guarantee.

        Concurrent callers for the same phone converge on one row: the loser
        of the INSERT race hits IntegrityError inside its own savepoint and
        re-reads the winner's row.
        """
        phone = normalize_phone(phone)
        try:
            return self.get(phone=phone), False
        except self.model.DoesNotExist:
            pass
        try:
            with transaction.atomic():
                return self._create(phone, None), True
        except IntegrityError:
            return self.get(phone=phone), False


class User(AbstractBaseUser, PermissionsMixin):
    """Phone-identified user. Authorization uses Django-native
    is_staff / is_superuser / groups / permissions (no custom RBAC)."""

    phone = models.CharField(max_length=16, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(phone__regex=CANONICAL_RE),
                name="accounts_user_phone_canonical",
            )
        ]

    def save(self, *args, **kwargs):
        # Deterministic normalization at the model boundary: no code path can
        # persist a non-canonical phone (the DB check constraint backs this up).
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.phone


class OTPChallenge(models.Model):
    """One issued one-time code. Only an HMAC of the code is stored."""

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login / signup"

    phone = models.CharField(max_length=16)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    salt = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["phone", "purpose", "-created_at"],
                name="otp_phone_purpose_created_idx",
            ),
            models.Index(fields=["expires_at"], name="otp_expires_at_idx"),
        ]
