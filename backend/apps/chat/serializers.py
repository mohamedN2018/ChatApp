"""Serializers for conversations and messages.

``MessageSerializer`` is deliberately viewer-agnostic so the exact same payload
can be broadcast to every participant over the channel layer; viewer-relative
data (unread counts, my-state) lives on ``ConversationSerializer``.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.profiles.serializers import PublicUserSerializer

from .models import Conversation, Message
from .services import aggregate_reactions


class ReplyPreviewSerializer(serializers.ModelSerializer):
    sender = PublicUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ("id", "sender", "type", "text", "deleted_for_everyone")
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    sender = PublicUserSerializer(read_only=True)
    reply_to = ReplyPreviewSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "sender",
            "type",
            "text",
            "reply_to",
            "reactions",
            "is_edited",
            "edited_at",
            "deleted_for_everyone",
            "metadata",
            "created_at",
        )
        read_only_fields = fields

    def get_reactions(self, obj) -> list:
        return aggregate_reactions(obj)


class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    my_state = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            "id",
            "type",
            "title",
            "participants",
            "last_message",
            "unread_count",
            "my_state",
            "last_message_at",
            "created_at",
        )
        read_only_fields = fields

    def _my_participant(self, obj):
        viewer = self.context["request"].user
        return next((p for p in obj.participants.all() if p.user_id == viewer.id), None)

    def get_participants(self, obj) -> list:
        users = [p.user for p in obj.participants.all() if p.left_at is None]
        return PublicUserSerializer(users, many=True).data

    def get_last_message(self, obj) -> dict | None:
        message = obj.messages.order_by("-created_at").first()
        return MessageSerializer(message).data if message else None

    def get_unread_count(self, obj) -> int:
        viewer = self.context["request"].user
        participant = self._my_participant(obj)
        if participant is None:
            return 0
        qs = obj.messages.exclude(sender=viewer)
        if participant.last_read_at:
            qs = qs.filter(created_at__gt=participant.last_read_at)
        if participant.cleared_at:
            qs = qs.filter(created_at__gt=participant.cleared_at)
        return qs.count()

    def get_my_state(self, obj) -> dict | None:
        participant = self._my_participant(obj)
        if participant is None:
            return None
        return {
            "is_pinned": participant.is_pinned,
            "is_archived": participant.is_archived,
            "is_muted": participant.is_muted,
            "last_read_at": participant.last_read_at,
        }


# ------------------------------------------------------------------- write inputs
class StartConversationSerializer(serializers.Serializer):
    username = serializers.CharField()


class MessageCreateSerializer(serializers.Serializer):
    text = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=False
    )
    reply_to = serializers.UUIDField(required=False, allow_null=True)
    client_id = serializers.CharField(required=False, allow_blank=True)


class MessageEditSerializer(serializers.Serializer):
    text = serializers.CharField()


class ReactionSerializer(serializers.Serializer):
    emoji = serializers.CharField(max_length=32)


class ConversationStateSerializer(serializers.Serializer):
    is_pinned = serializers.BooleanField(required=False)
    is_archived = serializers.BooleanField(required=False)
    is_muted = serializers.BooleanField(required=False)
