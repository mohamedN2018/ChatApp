"""
Presence WebSocket consumer.

Protocol (JSON messages):
  client -> server:
    {"action": "subscribe",   "user_ids": [...]}   watch these users' presence
    {"action": "unsubscribe", "user_ids": [...]}
    {"action": "set_status",  "status": "away"}     change own presence mode
    {"action": "heartbeat"}                          keep the connection's TTL alive
  server -> client:
    {"type": "presence.self",     "status": "..."}
    {"type": "presence.snapshot", "users": [{"user_id","status"}, ...]}
    {"type": "presence.update",   "user_id", "status", "last_seen"}

Fan-out model: updates *about* user X are published to the group ``presence.u.X``;
observers join that group via ``subscribe``. A user's own connect/disconnect/status
change publishes to their group, reaching exactly the observers who care.
"""

from __future__ import annotations

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.profiles.models import PresenceStatus
from apps.social.services import SocialService

from .presence import PresenceTracker, resolve_visible_status

WS_CLOSE_UNAUTHORIZED = 4401
_SETTABLE = {
    PresenceStatus.ONLINE,
    PresenceStatus.AWAY,
    PresenceStatus.BUSY,
    PresenceStatus.INVISIBLE,
}


def presence_group(uid) -> str:
    return f"presence.u.{uid}"


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        self.user = user
        self.uid = str(user.id)
        self.subscribed: set[str] = set()
        await self.accept()

        just_online = await sync_to_async(PresenceTracker.add_connection)(
            self.uid, self.channel_name
        )
        status = await self._effective_self_status()
        await self.send_json({"type": "presence.self", "status": status})
        if just_online:
            await self._broadcast(status)

    async def disconnect(self, code):
        if not hasattr(self, "uid"):
            return
        for group in self.subscribed:
            await self.channel_layer.group_discard(group, self.channel_name)
        went_offline = await sync_to_async(PresenceTracker.remove_connection)(
            self.uid, self.channel_name
        )
        if went_offline:
            await self._mark_last_seen()
            await self._broadcast(PresenceStatus.OFFLINE)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "subscribe":
            await self._subscribe(content.get("user_ids", []))
        elif action == "unsubscribe":
            await self._unsubscribe(content.get("user_ids", []))
        elif action == "set_status":
            await self._set_status(content.get("status"))
        elif action == "heartbeat":
            await sync_to_async(PresenceTracker.refresh)(self.uid)
            await self.send_json({"type": "pong"})

    # ----------------------------------------------------------------- internals
    async def _subscribe(self, user_ids) -> None:
        user_ids = [str(u) for u in user_ids][:200]
        for uid in user_ids:
            group = presence_group(uid)
            await self.channel_layer.group_add(group, self.channel_name)
            self.subscribed.add(group)
        snapshot = await self._snapshot(user_ids)
        await self.send_json({"type": "presence.snapshot", "users": snapshot})

    async def _unsubscribe(self, user_ids) -> None:
        for uid in user_ids:
            group = presence_group(str(uid))
            await self.channel_layer.group_discard(group, self.channel_name)
            self.subscribed.discard(group)

    async def _set_status(self, status) -> None:
        if status not in _SETTABLE:
            await self.send_json({"type": "error", "detail": "Invalid status."})
            return
        await self._save_status(status)
        effective = await self._effective_self_status()
        await self.send_json({"type": "presence.self", "status": effective})
        await self._broadcast(effective)

    async def _broadcast(self, status) -> None:
        payload = {"type": "presence.event", "user_id": self.uid, "status": str(status)}
        if status == PresenceStatus.OFFLINE:
            payload["last_seen"] = timezone.now().isoformat()
        await self.channel_layer.group_send(presence_group(self.uid), payload)

    async def presence_event(self, event) -> None:
        """Channel-layer handler -> forward to the client."""
        await self.send_json(
            {
                "type": "presence.update",
                "user_id": event["user_id"],
                "status": event["status"],
                "last_seen": event.get("last_seen"),
            }
        )

    # ------------------------------------------------------------- DB-bound helpers
    @database_sync_to_async
    def _save_status(self, status) -> None:
        profile = self.user.profile
        profile.status = status
        profile.save(update_fields=["status", "updated_at"])

    @database_sync_to_async
    def _mark_last_seen(self) -> None:
        get_user_model().objects.filter(pk=self.user.pk).update(last_seen_at=timezone.now())

    @database_sync_to_async
    def _effective_self_status(self) -> str:
        status = self.user.profile.status
        return PresenceStatus.OFFLINE if status == PresenceStatus.INVISIBLE else status

    @database_sync_to_async
    def _snapshot(self, user_ids) -> list[dict]:
        online = PresenceTracker.online_among(user_ids)
        users = (
            get_user_model().objects.filter(pk__in=user_ids).select_related("profile", "privacy")
        )
        snapshot = []
        for user in users:
            are_friends = SocialService.are_friends(self.user, user)
            status = resolve_visible_status(
                user, is_online=str(user.id) in online, are_friends=are_friends
            )
            snapshot.append({"user_id": str(user.id), "status": str(status)})
        return snapshot
