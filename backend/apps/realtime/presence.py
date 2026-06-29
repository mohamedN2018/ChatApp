"""
Redis-backed presence tracking.

A user is "online" while they hold at least one live WebSocket connection. Each
connection's channel name is held in a Redis SET per user (``presence:conns:{uid}``)
with a sliding TTL refreshed by client heartbeats, so a crashed client's entry
expires instead of pinning the user online forever. Counting connections (rather
than a boolean) means multiple tabs/devices behave correctly.

``resolve_visible_status`` combines live connectivity with the user's chosen
presence mode and privacy settings to decide what an observer may see.
"""

from __future__ import annotations

import redis
from django.conf import settings

from apps.profiles.models import PresenceStatus, Visibility

CONN_TTL_SECONDS = 120

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _key(uid) -> str:
    return f"presence:conns:{uid}"


class PresenceTracker:
    """Connection bookkeeping. All methods are synchronous (wrap for async use)."""

    @classmethod
    def add_connection(cls, uid, channel_name: str) -> bool:
        """Register a connection. Returns True if the user just came online."""
        client = get_client()
        key = _key(uid)
        was_offline = client.scard(key) == 0
        client.sadd(key, channel_name)
        client.expire(key, CONN_TTL_SECONDS)
        return was_offline

    @classmethod
    def remove_connection(cls, uid, channel_name: str) -> bool:
        """Drop a connection. Returns True if the user just went offline."""
        client = get_client()
        key = _key(uid)
        client.srem(key, channel_name)
        if client.scard(key) == 0:
            client.delete(key)
            return True
        return False

    @classmethod
    def refresh(cls, uid) -> None:
        get_client().expire(_key(uid), CONN_TTL_SECONDS)

    @classmethod
    def is_online(cls, uid) -> bool:
        return get_client().scard(_key(uid)) > 0

    @classmethod
    def online_among(cls, uids) -> set[str]:
        client = get_client()
        pipe = client.pipeline()
        uids = [str(u) for u in uids]
        for uid in uids:
            pipe.scard(_key(uid))
        counts = pipe.execute()
        return {uid for uid, count in zip(uids, counts, strict=True) if count > 0}


def resolve_visible_status(target_user, *, is_online: bool, are_friends: bool) -> str:
    """What presence an observer should see for ``target_user``.

    Honours the user's invisible mode and ``online_status_visibility`` privacy.
    Returns one of online/away/busy/offline.
    """
    if not is_online:
        return PresenceStatus.OFFLINE
    profile = target_user.profile
    if profile.status == PresenceStatus.INVISIBLE:
        return PresenceStatus.OFFLINE
    visibility = target_user.privacy.online_status_visibility
    if visibility == Visibility.NOBODY:
        return PresenceStatus.OFFLINE
    if visibility == Visibility.FRIENDS and not are_friends:
        return PresenceStatus.OFFLINE
    return profile.status
