"""Production settings. Fails fast when required configuration is missing."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, MIDDLEWARE, OTP_DELIVERY_BACKEND, SECRET_KEY, env, env_bool

DEBUG = False

# Django Admin static files: served by WhiteNoise from STATIC_ROOT, which the image build fills with
# `collectstatic`. Development settings are unaffected. Inserted right after SecurityMiddleware, as
# WhiteNoise requires.
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("A development SECRET_KEY must not be used in production.")
# .env.example ships a placeholder key for the development Compose stack; it must never reach production.
# Django's own `check --deploy` calls keys under 50 characters weak (CI runs it); here only clearly unusable
# values stop the process from booting. The key itself is never echoed.
_PLACEHOLDER_SECRET_KEYS = {"change-me", "changeme", "secret", "secret-key"}
if SECRET_KEY.strip().lower() in _PLACEHOLDER_SECRET_KEYS or len(SECRET_KEY) < 32:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is a known placeholder or shorter than 32 characters; "
        "set a long random value in production."
    )

if OTP_DELIVERY_BACKEND in {
    "apps.accounts.delivery.ConsoleDelivery",
    "apps.accounts.delivery.InMemoryDelivery",
}:
    raise ImproperlyConfigured("A dev/test OTP delivery backend must not be used in production.")

# TLS terminates at the CDN/WAF/Nginx edge; trust its forwarded protocol header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_REDIRECT_EXEMPT = [r"^api/health/"]

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# Keep 0 until HTTPS is verified end-to-end, then raise (e.g. 31536000).
SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "0") or 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
