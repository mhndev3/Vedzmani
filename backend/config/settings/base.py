"""Shared Django settings.

Environment-specific modules (dev / prod / test) import from here.
All configuration comes from environment variables; no secrets live in git.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def required(name: str) -> str:
    value = env(name)
    if value is None:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = env(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# PostgreSQL is the single source of truth (Django ORM). No second database.
DATABASES = {
    "default": dj_database_url.parse(
        required("DATABASE_URL"),
        conn_max_age=60,
        conn_health_checks=True,
    )
}

# Redis: cache / short-lived state ONLY. Never authoritative for
# inventory, orders or payments.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": required("REDIS_URL"),
        "KEY_PREFIX": "vedzmani",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cross-origin / CSRF. Default topology is same-origin behind Nginx, so CORS
# is closed unless origins are listed explicitly.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# --- Authentication (phone + OTP, Django session auth) ---------------------
# Public CDN base for product images (storage keys are stored, never URLs).
MEDIA_CDN_BASE_URL = env("MEDIA_CDN_BASE_URL", "")

AUTH_USER_MODEL = "accounts.User"

# Sessions live in PostgreSQL (Django default DB backend): auth state is never
# kept only in Redis, and logout really deletes the server-side session row.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = False
# "Remember me" lifetime; without it the session cookie dies with the browser.
AUTH_REMEMBER_ME_SECONDS = int(env("AUTH_REMEMBER_ME_SECONDS", str(60 * 60 * 24 * 30)))

OTP_TTL_SECONDS = int(env("OTP_TTL_SECONDS", "300"))
OTP_MAX_ATTEMPTS = int(env("OTP_MAX_ATTEMPTS", "5"))
OTP_REQUEST_COOLDOWN_SECONDS = int(env("OTP_REQUEST_COOLDOWN_SECONDS", "60"))
OTP_REQUEST_PHONE_LIMIT = int(env("OTP_REQUEST_PHONE_LIMIT", "5"))  # per hour
OTP_REQUEST_IP_LIMIT = int(env("OTP_REQUEST_IP_LIMIT", "20"))  # per hour
OTP_VERIFY_IP_LIMIT = int(env("OTP_VERIFY_IP_LIMIT", "30"))
OTP_VERIFY_IP_WINDOW_SECONDS = int(env("OTP_VERIFY_IP_WINDOW_SECONDS", "600"))
# Number of trusted reverse proxies in front of Django (Nginx = 1). 0 means
# X-Forwarded-For is ignored and REMOTE_ADDR is used for per-IP limits.
AUTH_TRUSTED_PROXY_COUNT = int(env("AUTH_TRUSTED_PROXY_COUNT", "0"))
# No SMS provider exists yet: the default REFUSES to send (never fakes success).
OTP_DELIVERY_BACKEND = env("OTP_DELIVERY_BACKEND", "apps.accounts.delivery.UnconfiguredDelivery")

# Secure by default: endpoints must opt in to being public.
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.SessionAuthentication401"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
