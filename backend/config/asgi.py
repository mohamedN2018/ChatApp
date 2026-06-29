"""
ASGI entrypoint.

Routes HTTP to the Django ASGI app and WebSocket traffic through the Channels
stack: origin validation -> JWT auth (from ?token=) -> URL router. Consumer
imports happen only after the Django app registry is initialised.
"""

from __future__ import annotations

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Initialise Django ASGI application early to populate the app registry before
# importing consumers/middleware that touch models.
django_asgi_app = get_asgi_application()

from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.realtime.middleware import JWTAuthMiddleware  # noqa: E402
from apps.realtime.routing import websocket_urlpatterns as presence_ws  # noqa: E402

websocket_urlpatterns = presence_ws + chat_ws

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        ),
    }
)
