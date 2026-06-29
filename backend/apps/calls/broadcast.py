"""Channel-layer helpers for call signaling and state events."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def call_user_group(uid) -> str:
    return f"call.user.{uid}"


def call_room_group(call_id) -> str:
    return f"call.room.{call_id}"


def _send(group: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:  # pragma: no cover
        return
    async_to_sync(layer.group_send)(group, {"type": "call.event", "payload": payload})


def send_to_users(user_ids, payload: dict) -> None:
    for uid in user_ids:
        _send(call_user_group(uid), payload)


def send_to_room(call_id, payload: dict) -> None:
    _send(call_room_group(call_id), payload)
