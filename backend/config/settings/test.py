"""Test settings: dev defaults, in-memory cache, fast hashing.

The database stays PostgreSQL (DATABASE_URL); no alternate DB engine is used.
"""

from .dev import *  # noqa: F401,F403

DEBUG = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
OTP_DELIVERY_BACKEND = "apps.accounts.delivery.InMemoryDelivery"
