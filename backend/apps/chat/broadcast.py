"""
Channel-layer fan-out for chat events.

Every conversation event is delivered to each participant's *personal* group
(``chat.user.{id}``) rather than a per-conversation group. This means a client
needs only one subscription (joined on connect) and newly created conversations
reach participants immediately without them having to join a new group — at the
cost of N sends per event, which is fine at 1:1/small-group scale and can be
optimised later for very large groups.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def user_group(uid) -> str:
    return f"chat.user.{uid}"


def broadcast_to_users(user_ids, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:  # pragma: no cover - misconfiguration
        return
    event = {"type": "chat.event", "payload": payload}
    for uid in user_ids:
        async_to_sync(layer.group_send)(user_group(uid), event)


def broadcast_to_conversation(conversation, payload: dict) -> None:
    broadcast_to_users(conversation.participant_user_ids(), payload)
