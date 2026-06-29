"""
Call signaling WebSocket consumer.

Relays WebRTC SDP/ICE between peers and tracks call state. Media is peer-to-peer
and never reaches the server. Each socket joins its personal group
``call.user.{id}`` (for incoming-call + targeted signaling) and, while in a call,
the room group ``call.room.{call_id}`` (for peer join/leave/state).

Client -> server: join, leave, signal (to a specific peer), state.
Server -> client (via ``call.event``): call.incoming, call.accepted, call.rejected,
peer.joined, peer.left, peer.state, call.signal, call.ended.
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import APIException

from .broadcast import call_room_group, call_user_group
from .models import Call
from .services import CallService

WS_CLOSE_UNAUTHORIZED = 4401


class CallConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        self.user = user
        self.uid = str(user.id)
        self.rooms: set[str] = set()
        await self.channel_layer.group_add(call_user_group(self.uid), self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if not hasattr(self, "uid"):
            return
        await self.channel_layer.group_discard(call_user_group(self.uid), self.channel_name)
        # Leave any active call rooms (and mark left in the DB).
        for call_id in list(self.rooms):
            await self.channel_layer.group_discard(call_room_group(call_id), self.channel_name)
            await self._leave(call_id)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        try:
            if action == "join":
                await self._join(content.get("call_id"))
            elif action == "leave":
                await self._leave(content.get("call_id"))
            elif action == "signal":
                await self._signal(content)
            elif action == "state":
                await self._state(content)
            else:
                await self.send_json({"event": "error", "detail": "Unknown action."})
        except APIException as exc:
            await self.send_json({"event": "error", "detail": str(exc.detail)})
        except Call.DoesNotExist:
            await self.send_json({"event": "error", "detail": "Call not found."})

    # ------------------------------------------------------------- group handler
    async def call_event(self, event):
        await self.send_json(event["payload"])

    # ----------------------------------------------------------------- actions
    async def _join(self, call_id):
        if not call_id:
            return
        await self.channel_layer.group_add(call_room_group(call_id), self.channel_name)
        self.rooms.add(str(call_id))
        await self._do_join(call_id)

    @database_sync_to_async
    def _do_join(self, call_id):
        CallService.join(user=self.user, call=Call.objects.get(pk=call_id))

    async def _leave(self, call_id):
        if not call_id:
            return
        await self.channel_layer.group_discard(call_room_group(call_id), self.channel_name)
        self.rooms.discard(str(call_id))
        await self._do_leave(call_id)

    @database_sync_to_async
    def _do_leave(self, call_id):
        call = Call.objects.filter(pk=call_id).first()
        if call is not None:
            CallService.leave(user=self.user, call=call)

    async def _signal(self, content):
        await self._do_signal(
            content.get("call_id"), content.get("to_user_id"), content.get("data")
        )

    @database_sync_to_async
    def _do_signal(self, call_id, to_user_id, data):
        if not (call_id and to_user_id):
            return
        CallService.relay_signal(
            from_user=self.user, call=Call.objects.get(pk=call_id), to_user_id=to_user_id, data=data
        )

    async def _state(self, content):
        await self._do_state(content)

    @database_sync_to_async
    def _do_state(self, content):
        call_id = content.get("call_id")
        if not call_id:
            return
        CallService.update_media_state(
            user=self.user,
            call=Call.objects.get(pk=call_id),
            is_muted=content.get("is_muted"),
            is_video_on=content.get("is_video_on"),
            hand_raised=content.get("hand_raised"),
        )
