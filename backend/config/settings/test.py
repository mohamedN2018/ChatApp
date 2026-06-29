"""
Test settings: fast and hermetic.

Uses SQLite + in-memory channel layer + local-memory cache so the unit suite
runs without Postgres/Redis. Integration tests that need the real services run
inside Docker against the development settings.
"""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

# A >=32-byte key so SimpleJWT's HMAC signing doesn't emit a length warning.
SECRET_KEY = "test-secret-key-not-for-production-min-32-bytes-long"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# Fast password hashing for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable throttling by default in tests (rate=None => always allowed). The
# dedicated throttle test re-enables a low rate via override_settings.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = dict.fromkeys(  # noqa: F405
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]  # noqa: F405
)

# Run Celery tasks synchronously in-process during tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Keep media off disk during tests.
MEDIA_ROOT = BASE_DIR / "test-media"  # noqa: F405
