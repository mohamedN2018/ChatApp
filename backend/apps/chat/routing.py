"""Chat WebSocket routes."""

from __future__ import annotations

from django.urls import path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat/", ChatConsumer.as_asgi()),
]
