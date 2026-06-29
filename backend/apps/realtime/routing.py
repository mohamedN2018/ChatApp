"""WebSocket URL routes. Chat/call consumers are appended here in later phases."""

from __future__ import annotations

from django.urls import path

from .consumers import PresenceConsumer

websocket_urlpatterns = [
    path("ws/presence/", PresenceConsumer.as_asgi()),
]
