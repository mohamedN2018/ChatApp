from __future__ import annotations

from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message, MessageReaction


class ParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    raw_id_fields = ("user",)
    readonly_fields = ("joined_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "title", "last_message_at", "created_at")
    list_filter = ("type",)
    search_fields = ("id", "title", "direct_key")
    inlines = [ParticipantInline]
    readonly_fields = ("direct_key", "created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "type",
        "is_edited",
        "deleted_for_everyone",
        "created_at",
    )
    list_filter = ("type", "is_edited", "deleted_for_everyone")
    search_fields = ("id", "text", "sender__username")
    raw_id_fields = ("conversation", "sender", "reply_to")
    date_hierarchy = "created_at"


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "emoji", "created_at")
    search_fields = ("user__username", "emoji")
    raw_id_fields = ("message", "user")
