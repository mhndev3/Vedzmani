"""User + OTP challenge models.

PostgreSQL is the source of truth for both. Redis is only used for
rate-limit counters (see ratelimit.py), never for authentication state.
"""

from django.conf import settings
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
    first_name = models.CharField(max_length=150, blank=True, default="", db_default="")
    last_name = models.CharField(max_length=150, blank=True, default="", db_default="")
    address = models.TextField(blank=True, default="", db_default="")
    postal_code = models.CharField(max_length=20, blank=True, default="", db_default="")
    national_code = models.CharField(max_length=10, null=True, blank=True, unique=True)
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
            ),
            models.CheckConstraint(
                condition=models.Q(national_code__isnull=True) | models.Q(national_code__regex=r"^[0-9]{10}$"),
                name="accounts_user_national_code_10_digits",
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
        LOGIN = "login", "Password login second factor"
        SIGNUP = "signup", "New customer registration"
        PASSWORD_RESET = "password_reset", "Password recovery"

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



class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_WAITING_CUSTOMER = "waiting_customer"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"), (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_WAITING_CUSTOMER, "Waiting for customer"),
        (STATUS_RESOLVED, "Resolved"), (STATUS_CLOSED, "Closed"),
    ]
    CATEGORY_CHOICES = [
        ("order", "Order"), ("shipping", "Shipping"),
        ("product", "Product"), ("payment", "Payment"), ("other", "Other"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_tickets")
    subject = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["status", "-updated_at"], name="support_status_updated_idx")]

    def __str__(self):
        return f"ticket:{self.pk}"


class SupportTicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_messages")
    body = models.TextField(max_length=5000)
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["ticket", "created_at"], name="support_msg_ticket_created_idx")]

