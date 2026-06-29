"""
ASGI entrypoint.

Routes HTTP to the Django ASGI app and WebSocket traffic through the Channels
stack. The WebSocket URLRouter is intentionally empty for Phase 0; realtime
consumers are added in the chat phase. JWT WebSocket auth middleware is wired
in then as well.
"""

from __future__ import annotations

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Initialise Django ASGI application early to populate the app registry before
# importing anything that touches models/consumers.
django_asgi_app = get_asgi_application()

# WebSocket routes are registered here as features land (chat, calls, presence).
websocket_urlpatterns: list = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            URLRouter(websocket_urlpatterns),
        ),
    }
)
