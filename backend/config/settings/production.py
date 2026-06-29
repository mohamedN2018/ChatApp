"""Production settings: strict security, S3/MinIO storage, real email."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = False

# Hosts/origins must be set explicitly via env in production — no wildcards.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # noqa: F405  (raises if unset)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# --- HTTPS / transport security ---
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --- Media via S3/MinIO ---
# Object storage is enabled via USE_S3 (see base.py); production requires it.
if not USE_S3:  # noqa: F405
    raise RuntimeError("USE_S3 must be true in production (set it in the environment).")

# --- Real SMTP email ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405

# --- Error monitoring (optional) ---
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_RATE", default=0.1),  # noqa: F405
        send_default_pii=False,
    )
