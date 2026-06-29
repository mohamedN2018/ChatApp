"""
Chat service layer.

Owns conversation/message lifecycle and, crucially, the realtime broadcast: a
message sent over REST or over WebSocket flows through the same code path and is
pushed to every participant's channel-layer group. Views/consumers stay thin.
"""

from __future__ import annotations

import json

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.utils.encoders import JSONEncoder as DRFJSONEncoder

from apps.social.services import SocialService

from .broadcast import broadcast_to_conversation
from .models import (
    Conversation,
    ConversationParticipant,
    ConversationType,
    Message,
    MessageAttachment,
    MessageReaction,
    MessageType,
)


def aggregate_reactions(message: Message) -> list[dict]:
    """Group a message's reactions as ``[{emoji, count, user_ids}]``."""
    grouped: dict[str, dict] = {}
    for reaction in message.reactions.all():
        entry = grouped.setdefault(
            reaction.emoji, {"emoji": reaction.emoji, "count": 0, "user_ids": []}
        )
        entry["count"] += 1
        entry["user_ids"].append(str(reaction.user_id))
    return list(grouped.values())


class ChatService:
    # ----------------------------------------------------------- membership guard
    @staticmethod
    def _ensure_participant(conversation: Conversation, user) -> ConversationParticipant:
        participant = ConversationParticipant.objects.filter(
            conversation=conversation, user=user, left_at__isnull=True
        ).first()
        if participant is None:
            raise PermissionDenied("You are not a participant in this conversation.")
        return participant

    # ----------------------------------------------------------------- conversations
    @classmethod
    def get_or_create_direct(cls, *, user_a, user_b) -> Conversation:
        if user_a == user_b:
            raise ValidationError("You cannot start a conversation with yourself.")
        if SocialService.is_blocked_between(user_a, user_b):
            raise PermissionDenied("This action is not allowed.")
        key = Conversation.direct_key_for(user_a.id, user_b.id)
        existing = Conversation.objects.filter(direct_key=key).first()
        if existing is not None:
            return existing
        try:
            with transaction.atomic():
                conversation = Conversation.objects.create(
                    type=ConversationType.DIRECT, direct_key=key
                )
                ConversationParticipant.objects.bulk_create(
                    [
                        ConversationParticipant(conversation=conversation, user=user_a),
                        ConversationParticipant(conversation=conversation, user=user_b),
                    ]
                )
                return conversation
        except IntegrityError:
            # Lost a race; the other creator won.
            return Conversation.objects.get(direct_key=key)

    # ---------------------------------------------------------------------- messages
    @classmethod
    @transaction.atomic
    def send_message(
        cls,
        *,
        sender,
        conversation,
        text="",
        reply_to=None,
        message_type=MessageType.TEXT,
        metadata=None,
        attachment_ids=None,
    ) -> Message:
        cls._ensure_participant(conversation, sender)
        text = (text or "").strip()
        attachment_ids = list(dict.fromkeys(attachment_ids or []))  # de-dupe, keep order
        if not text and not attachment_ids:
            raise ValidationError("A message must have text or at least one attachment.")
        if reply_to is not None and reply_to.conversation_id != conversation.id:
            raise ValidationError("Cannot reply to a message from another conversation.")

        medias = []
        if attachment_ids:
            from apps.media.models import MediaFile

            found = {
                str(m.id): m for m in MediaFile.objects.filter(pk__in=attachment_ids, owner=sender)
            }
            if len(found) != len(attachment_ids):
                raise ValidationError("One or more attachments are invalid or not yours.")
            medias = [found[str(aid)] for aid in attachment_ids]
            message_type = medias[0].kind  # MediaKind values map 1:1 to MessageType

        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            type=message_type,
            text=text,
            reply_to=reply_to,
            metadata=metadata or {},
        )
        for order, media in enumerate(medias):
            MessageAttachment.objects.create(message=message, media=media, order=order)
        conversation.touch_last_message(message.created_at)
        # The sender has, by definition, read up to their own message.
        ConversationParticipant.objects.filter(conversation=conversation, user=sender).update(
            last_read_at=message.created_at, last_delivered_at=message.created_at
        )
        cls._broadcast(conversation, {"event": "message.new", "message": cls._serialize(message)})
        return message

    @classmethod
    def edit_message(cls, *, actor, message, text) -> Message:
        if message.sender_id != actor.id:
            raise PermissionDenied("You can only edit your own messages.")
        if message.deleted_for_everyone:
            raise ValidationError("This message has been deleted.")
        text = (text or "").strip()
        if not text:
            raise ValidationError("Message text cannot be empty.")
        message.mark_edited(text)
        cls._broadcast(
            message.conversation,
            {"event": "message.update", "message": cls._serialize(message)},
        )
        return message

    @classmethod
    def delete_message(cls, *, actor, message, for_everyone: bool) -> None:
        if for_everyone:
            if message.sender_id != actor.id:
                raise PermissionDenied("You can only delete your own messages for everyone.")
            message.delete_for_everyone()
            message.reactions.all().delete()
            cls._broadcast(
                message.conversation,
                {
                    "event": "message.delete",
                    "message_id": str(message.id),
                    "conversation_id": str(message.conversation_id),
                    "for_everyone": True,
                },
            )
        else:
            cls._ensure_participant(message.conversation, actor)
            message.hidden_for.add(actor)  # affects only this user

    @classmethod
    def toggle_reaction(cls, *, actor, message, emoji: str) -> Message:
        cls._ensure_participant(message.conversation, actor)
        existing = MessageReaction.objects.filter(message=message, user=actor, emoji=emoji).first()
        if existing is not None:
            existing.delete()
        else:
            MessageReaction.objects.create(message=message, user=actor, emoji=emoji)
        cls._broadcast(
            message.conversation,
            {
                "event": "reaction.update",
                "message_id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "reactions": aggregate_reactions(message),
            },
        )
        return message

    @classmethod
    def mark_read(cls, *, actor, conversation) -> None:
        cls._ensure_participant(conversation, actor)
        now = timezone.now()
        ConversationParticipant.objects.filter(conversation=conversation, user=actor).update(
            last_read_at=now
        )
        cls._broadcast(
            conversation,
            {
                "event": "read",
                "conversation_id": str(conversation.id),
                "user_id": str(actor.id),
                "last_read_at": now.isoformat(),
            },
        )

    # -------------------------------------------------------------------- internals
    @staticmethod
    def _serialize(message: Message) -> dict:
        # The channel layer must carry JSON/msgpack-safe primitives, but DRF's
        # `.data` holds raw UUID/datetime objects. Round-trip through DRF's
        # encoder so UUIDs/datetimes become strings before they hit the layer.
        from .serializers import MessageSerializer

        data = MessageSerializer(message).data
        return json.loads(json.dumps(data, cls=DRFJSONEncoder))

    @staticmethod
    def _broadcast(conversation, payload: dict) -> None:
        payload.setdefault("conversation_id", str(conversation.id))
        broadcast_to_conversation(conversation, payload)
