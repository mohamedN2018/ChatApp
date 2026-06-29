"""
JWT authentication middleware for Channels (WebSocket).

Authenticates the connection from a short-lived access token supplied as a query
parameter (``?token=…``) — the browser WebSocket API can't set Authorization
headers, so the query string is the standard channel. The same session-revocation
check used for HTTP applies here, so a revoked session can't open a socket.
"""

from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.tokens import is_session_revoked


@database_sync_to_async
def _get_user(token: str | None):
    User = get_user_model()
    if not token:
        return AnonymousUser()
    try:
        access = AccessToken(token)
    except TokenError:
        return AnonymousUser()
    sid = access.get("sid")
    if sid and is_session_revoked(str(sid)):
        return AnonymousUser()
    try:
        return User.objects.get(pk=access["user_id"], is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    """Populates ``scope['user']`` from a JWT access token in the query string."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        scope["user"] = await _get_user(token)
        return await self.inner(scope, receive, send)
