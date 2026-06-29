from __future__ import annotations

from django.contrib import admin

from .models import Call, CallParticipant


class ParticipantInline(admin.TabularInline):
    model = CallParticipant
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "status", "initiator", "started_at", "ended_at", "created_at")
    list_filter = ("type", "status")
    search_fields = ("id", "initiator__username")
    raw_id_fields = ("conversation", "initiator")
    inlines = [ParticipantInline]
    date_hierarchy = "created_at"


@admin.register(CallParticipant)
class CallParticipantAdmin(admin.ModelAdmin):
    list_display = ("call", "user", "state", "is_muted", "is_video_on", "hand_raised")
    list_filter = ("state",)
    raw_id_fields = ("call", "user")
