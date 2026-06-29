"""Auto-provision a Profile + privacy/notification settings for every new user."""

from __future__ import annotations

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import NotificationSettings, PrivacySettings, Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="provision_profile")
def provision_user_side_tables(sender, instance, created, **kwargs) -> None:
    if not created:
        return
    Profile.objects.get_or_create(user=instance)
    PrivacySettings.objects.get_or_create(user=instance)
    NotificationSettings.objects.get_or_create(user=instance)
