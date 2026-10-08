"""Local development settings. Safe defaults for a developer machine ONLY."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-only-insecure-key-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgres://vedzmani:vedzmani@localhost:5432/vedzmani")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: E402,F401,F403
from .base import ALLOWED_HOSTS as _ALLOWED_HOSTS  # noqa: E402
from .base import env_bool  # noqa: E402

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _ALLOWED_HOSTS or ["localhost", "127.0.0.1"]
