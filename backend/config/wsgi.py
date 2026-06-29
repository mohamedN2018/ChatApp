"""WSGI entrypoint (sync). ASGI/Channels is the primary server; this exists for
tooling and any sync-only deployment target."""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_wsgi_application()
