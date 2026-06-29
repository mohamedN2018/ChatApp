"""
Profile, privacy, and notification models.

The ``User`` table stays narrow (identity/auth); everything a person *fills in*
lives here in a 1:1 ``Profile``, with privacy and notification preferences split
into their own 1:1 tables so they can grow without bloating the profile row.

Presence: ``Profile.status`` stores the user's chosen presence *mode*
(online/away/busy/invisible). Whether they're actually connected is tracked in
Redis (see apps.realtime.presence); the effective presence shown to others
combines the two.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel


def avatar_upload_to(instance: Profile, filename: str) -> str:
    return f"avatars/{instance.user_id}/{filename}"


def cover_upload_to(instance: Profile, filename: str) -> str:
    return f"covers/{instance.user_id}/{filename}"


class PresenceStatus(models.TextChoices):
    ONLINE = "online", _("Online")
    AWAY = "away", _("Away")
    BUSY = "busy", _("Busy")
    INVISIBLE = "invisible", _("Invisible")
    OFFLINE = "offline", _("Offline")


class Visibility(models.TextChoices):
    EVERYONE = "everyone", _("Everyone")
    FRIENDS = "friends", _("Friends only")
    NOBODY = "nobody", _("Nobody")


class Profile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to=avatar_upload_to, null=True, blank=True)
    cover = models.ImageField(upload_to=cover_upload_to, null=True, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2")
    language = models.CharField(max_length=10, default="en")
    website = models.URLField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    # e.g. {"twitter": "...", "github": "...", "instagram": "..."}
    social_links = models.JSONField(default=dict, blank=True)
    # Presence mode the user prefers when connected.
    status = models.CharField(
        max_length=12, choices=PresenceStatus.choices, default=PresenceStatus.ONLINE
    )
    custom_status_text = models.CharField(max_length=128, blank=True)
    custom_status_emoji = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "profiles_profile"

    def __str__(self) -> str:
        return f"Profile<@{self.user.username}>"


class PrivacySettings(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privacy",
    )
    profile_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    last_seen_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    online_status_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    who_can_follow = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    who_can_friend_request = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    who_can_message = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.EVERYONE
    )
    searchable = models.BooleanField(default=True)

    class Meta:
        db_table = "profiles_privacy_settings"
        verbose_name_plural = "privacy settings"

    def __str__(self) -> str:
        return f"Privacy<@{self.user.username}>"


class NotificationSettings(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )
    email_messages = models.BooleanField(default=True)
    email_friend_requests = models.BooleanField(default=True)
    email_mentions = models.BooleanField(default=True)
    push_messages = models.BooleanField(default=True)
    push_friend_requests = models.BooleanField(default=True)
    push_mentions = models.BooleanField(default=True)
    push_calls = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "profiles_notification_settings"
        verbose_name_plural = "notification settings"

    def __str__(self) -> str:
        return f"Notifications<@{self.user.username}>"
