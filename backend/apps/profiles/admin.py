from __future__ import annotations

from django.contrib import admin

from .models import NotificationSettings, PrivacySettings, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "country", "language", "created_at")
    list_filter = ("status", "language")
    search_fields = ("user__username", "user__email", "bio")
    raw_id_fields = ("user",)


@admin.register(PrivacySettings)
class PrivacySettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "profile_visibility", "last_seen_visibility", "searchable")
    list_filter = ("profile_visibility", "searchable")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "email_messages", "push_messages", "sound_enabled")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)
