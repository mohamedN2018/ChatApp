"""Development settings: verbose, permissive, fast feedback loops."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Console email backend: verification/reset links print to the runserver log.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Browsable API is handy locally.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# Loosen throttles so local testing isn't rate-limited into the ground.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "1000/min",
    "user": "10000/min",
    "login": "100/min",
    "register": "100/min",
    "verify_email": "100/min",
    "resend_verification": "100/min",
    "password_reset": "100/min",
}

CORS_ALLOW_ALL_ORIGINS = True
