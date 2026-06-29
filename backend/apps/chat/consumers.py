"""
Chat WebSocket consumer.

One socket per user. On connect the user joins their personal group
``chat.user.{id}``; ChatService broadcasts every conversation event to the
personal groups of all participants, so this consumer simply forwards them.

Client -> server actions: send, typing, read, react, edit, delete.
Server -> client events (via ``chat.event``): message.new, message.update,
message.delete, reaction.update, read, typing, error.
"""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import APIException

from .broadcast import user_group
from .models import Conversation, Message
from .services import ChatService

WS_CLOSE_UNAUTHORIZED = 4401


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        self.user = user
        self.uid = str(user.id)
        self.group = user_group(self.uid)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        try:
            if action == "send":
                await self._send(content)
            elif action == "typing":
                await self._typing(content)
            elif action == "read":
                await self._read(content)
            elif action == "react":
                await self._react(content)
            elif action == "edit":
                await self._edit(content)
            elif action == "delete":
                await self._delete(content)
            else:
                await self.send_json({"event": "error", "detail": "Unknown action."})
        except APIException as exc:
            await self.send_json(
                {"event": "error", "detail": str(exc.detail), "client_id": content.get("client_id")}
            )
        except (Conversation.DoesNotExist, Message.DoesNotExist):
            await self.send_json({"event": "error", "detail": "Not found."})

    # --------------------------------------------------------------- group handler
    async def chat_event(self, event):
        await self.send_json(event["payload"])

    # ----------------------------------------------------------------- DB actions
    async def _send(self, content):
        await self._do_send(
            content.get("conversation_id"),
            content.get("text", ""),
            content.get("reply_to"),
            content.get("client_id", ""),
        )

    @database_sync_to_async
    def _do_send(self, conversation_id, text, reply_to_id, client_id):
        conversation = Conversation.objects.get(pk=conversation_id)
        reply_to = (
            Message.objects.filter(pk=reply_to_id, conversation=conversation).first()
            if reply_to_id
            else None
        )
        metadata = {"client_id": client_id} if client_id else {}
        ChatService.send_message(
            sender=self.user,
            conversation=conversation,
            text=text,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def _read(self, content):
        await self._do_read(content.get("conversation_id"))

    @database_sync_to_async
    def _do_read(self, conversation_id):
        conversation = Conversation.objects.get(pk=conversation_id)
        ChatService.mark_read(actor=self.user, conversation=conversation)

    async def _react(self, content):
        await self._do_react(content.get("message_id"), content.get("emoji", ""))

    @database_sync_to_async
    def _do_react(self, message_id, emoji):
        message = Message.objects.get(pk=message_id)
        ChatService.toggle_reaction(actor=self.user, message=message, emoji=emoji)

    async def _edit(self, content):
        await self._do_edit(content.get("message_id"), content.get("text", ""))

    @database_sync_to_async
    def _do_edit(self, message_id, text):
        message = Message.objects.get(pk=message_id)
        ChatService.edit_message(actor=self.user, message=message, text=text)

    async def _delete(self, content):
        await self._do_delete(content.get("message_id"), bool(content.get("for_everyone")))

    @database_sync_to_async
    def _do_delete(self, message_id, for_everyone):
        message = Message.objects.get(pk=message_id)
        ChatService.delete_message(actor=self.user, message=message, for_everyone=for_everyone)

    # --------------------------------------------------------------- typing (live)
    async def _typing(self, content):
        conversation_id = content.get("conversation_id")
        state = content.get("state", "start")
        other_ids = await self._other_participant_ids(conversation_id)
        payload = {
            "event": "typing",
            "conversation_id": str(conversation_id),
            "user_id": self.uid,
            "state": state,
        }
        for uid in other_ids:
            await self.channel_layer.group_send(
                user_group(uid), {"type": "chat.event", "payload": payload}
            )

    @database_sync_to_async
    def _other_participant_ids(self, conversation_id) -> list:
        conversation = Conversation.objects.filter(pk=conversation_id).first()
        if conversation is None:
            return []
        ids = conversation.participant_user_ids()
        # Only members may emit typing, and never echo to self.
        if self.user.id not in ids:
            return []
        return [str(uid) for uid in ids if str(uid) != self.uid]
