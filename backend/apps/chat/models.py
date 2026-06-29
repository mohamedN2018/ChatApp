"""
Chat domain: conversations, per-participant state, messages, reactions.

Phase 3 focuses on 1:1 (direct) conversations; the schema already carries a
``type`` and group-capable participant roles so group chat (Phase 5) slots in
without migrations churn.

Two distinct notions of "deleted" on a message:
  * ``is_deleted`` (from BaseModel) — hard removal / moderation; hidden everywhere.
  * ``deleted_for_everyone`` — user action; the row survives as a tombstone
    ("This message was deleted") so the conversation stays coherent.
  * ``hidden_for`` (M2M) — "delete for me"; hidden only for those users.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


class ConversationType(models.TextChoices):
    DIRECT = "direct", _("Direct")
    GROUP = "group", _("Group")


class Conversation(BaseModel):
    type = models.CharField(
        max_length=10, choices=ConversationType.choices, default=ConversationType.DIRECT
    )
    # Canonical "low:high" user-id key for direct conversations, enforcing one
    # direct conversation per pair. Null for group conversations.
    direct_key = models.CharField(max_length=73, null=True, blank=True, unique=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Group fields (populated in the groups phase; harmless nulls for direct).
    title = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_conversations"
    )

    class Meta:
        db_table = "chat_conversation"
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self) -> str:
        return f"Conversation<{self.type}:{self.id}>"

    @staticmethod
    def direct_key_for(user_a_id, user_b_id) -> str:
        lo, hi = sorted([str(user_a_id), str(user_b_id)])
        return f"{lo}:{hi}"

    def participant_user_ids(self) -> list:
        return list(
            self.participants.filter(left_at__isnull=True).values_list("user_id", flat=True)
        )

    def touch_last_message(self, when=None) -> None:
        self.last_message_at = when or timezone.now()
        self.save(update_fields=["last_message_at", "updated_at"])


class ParticipantRole(models.TextChoices):
    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    MEMBER = "member", _("Member")


class ConversationParticipant(UUIDModel, TimeStampedModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        USER, on_delete=models.CASCADE, related_name="conversation_participations"
    )
    role = models.CharField(
        max_length=10, choices=ParticipantRole.choices, default=ParticipantRole.MEMBER
    )
    # Read/delivery cursors power unread counts and receipts.
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_delivered_at = models.DateTimeField(null=True, blank=True)
    # Per-user conversation state.
    is_archived = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)  # "clear history" for me
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_conversation_participant"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="uniq_conversation_participant"
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_archived"]),
            models.Index(fields=["conversation", "left_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.conversation_id}"


class MessageType(models.TextChoices):
    TEXT = "text", _("Text")
    IMAGE = "image", _("Image")
    VIDEO = "video", _("Video")
    AUDIO = "audio", _("Audio")
    VOICE = "voice", _("Voice note")
    FILE = "file", _("File")
    SYSTEM = "system", _("System")


class Message(BaseModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_messages"
    )
    type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    text = models.TextField(blank=True)
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_for_everyone = models.BooleanField(default=False)
    hidden_for = models.ManyToManyField(USER, related_name="hidden_messages", blank=True)
    # client-supplied id (optimistic UI dedupe), mentions, etc.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
            models.Index(fields=["sender"]),
        ]

    def __str__(self) -> str:
        return f"Message<{self.id}> in {self.conversation_id}"

    def mark_edited(self, text: str) -> None:
        self.text = text
        self.is_edited = True
        self.edited_at = timezone.now()
        self.save(update_fields=["text", "is_edited", "edited_at", "updated_at"])

    def delete_for_everyone(self) -> None:
        self.deleted_for_everyone = True
        self.text = ""
        self.save(update_fields=["deleted_for_everyone", "text", "updated_at"])


class MessageAttachment(UUIDModel, TimeStampedModel):
    """Links a message to an uploaded media file (images, video, voice, files)."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    media = models.ForeignKey(
        "media.MediaFile", on_delete=models.CASCADE, related_name="message_attachments"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "chat_message_attachment"
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["message", "media"], name="uniq_message_media")
        ]

    def __str__(self) -> str:
        return f"attachment {self.media_id} on {self.message_id}"


class MessageReaction(UUIDModel, TimeStampedModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="message_reactions")
    emoji = models.CharField(max_length=32)

    class Meta:
        db_table = "chat_message_reaction"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"], name="uniq_message_user_emoji"
            )
        ]
        indexes = [models.Index(fields=["message"])]

    def __str__(self) -> str:
        return f"{self.user_id} {self.emoji} on {self.message_id}"
