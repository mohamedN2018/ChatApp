"""
JWT issuance bound to a server-side session, plus immediate-revocation support.

Each issued token carries a ``sid`` claim (the UserSession id). Because the claim
is copied onto the derived access token, a session can be revoked server-side and
enforced instantly via a short-lived Redis flag — without waiting for the access
token to expire. The flag's TTL equals the access-token lifetime, after which the
token is invalid anyway and the flag is no longer needed.
"""

from __future__ import annotations

from django.core.cache import cache
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

SESSION_CLAIM = "sid"
_REVOKED_PREFIX = "revoked_session:"


def build_tokens_for_session(session) -> tuple[str, str]:
    """Issue an (access, refresh) pair for the user, tagged with the session id.

    Custom claims set on the refresh token are copied onto the access token by
    SimpleJWT, so ``sid``/``username`` are available on both.
    """
    user = session.user
    refresh = RefreshToken.for_user(user)
    refresh[SESSION_CLAIM] = str(session.id)
    refresh["username"] = user.username
    refresh["email_verified"] = user.is_email_verified
    return str(refresh.access_token), str(refresh)


def _revoked_key(sid: str) -> str:
    return f"{_REVOKED_PREFIX}{sid}"


def mark_session_revoked(sid: str) -> None:
    """Flag a session as revoked for the duration of the access-token lifetime."""
    ttl = int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())
    cache.set(_revoked_key(str(sid)), True, timeout=ttl)


def is_session_revoked(sid: str) -> bool:
    return bool(cache.get(_revoked_key(str(sid))))
