"""Production settings. Fails fast when required configuration is missing."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, SECRET_KEY, env, env_bool

DEBUG = False

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("A development SECRET_KEY must not be used in production.")

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
