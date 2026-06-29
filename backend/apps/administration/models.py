"""
Administration & moderation: reports, feature flags, announcements, a singleton
system config (maintenance mode etc.), and an admin audit log.

These power the admin panel (Phase 8 UI) and platform hardening: abuse reporting,
runtime feature toggles, broadcast announcements, and a kill-switch maintenance
mode enforced by middleware.
"""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


class ReportTargetType(models.TextChoices):
    USER = "user", _("User")
    MESSAGE = "message", _("Message")
    GROUP = "group", _("Group")


class ReportStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    REVIEWING = "reviewing", _("Reviewing")
    RESOLVED = "resolved", _("Resolved")
    DISMISSED = "dismissed", _("Dismissed")


class Report(BaseModel):
    reporter = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, related_name="reports_made"
    )
    target_type = models.CharField(max_length=10, choices=ReportTargetType.choices)
    target_id = models.UUIDField()
    reason = models.CharField(max_length=60)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=ReportStatus.choices, default=ReportStatus.PENDING, db_index=True
    )
    handled_by = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_handled"
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = "admin_report"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"Report<{self.target_type}:{self.reason}:{self.status}>"


class FeatureFlag(UUIDModel, TimeStampedModel):
    key = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = "admin_feature_flag"
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key}={'on' if self.is_enabled else 'off'}"

    @staticmethod
    def is_active(key: str) -> bool:
        flag = FeatureFlag.objects.filter(key=key).first()
        return bool(flag and flag.is_enabled)


class AnnouncementLevel(models.TextChoices):
    INFO = "info", _("Info")
    WARNING = "warning", _("Warning")
    CRITICAL = "critical", _("Critical")


class Announcement(BaseModel):
    title = models.CharField(max_length=160)
    body = models.TextField()
    level = models.CharField(
        max_length=10, choices=AnnouncementLevel.choices, default=AnnouncementLevel.INFO
    )
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "admin_announcement"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Announcement<{self.title}>"


class SystemConfig(UUIDModel, TimeStampedModel):
    """Singleton platform configuration. Use :meth:`get_solo`."""

    CACHE_KEY = "system_config"

    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default="We'll be back shortly.")
    signups_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "admin_system_config"

    def __str__(self) -> str:
        return f"SystemConfig(maintenance={self.maintenance_mode})"

    @classmethod
    def get_solo(cls) -> SystemConfig:
        config = cache.get(cls.CACHE_KEY)
        if config is None:
            config = cls.objects.first() or cls.objects.create()
            cache.set(cls.CACHE_KEY, config, timeout=30)
        return config

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)


class AdminAuditLog(UUIDModel, TimeStampedModel):
    actor = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, related_name="admin_actions"
    )
    action = models.CharField(max_length=60, db_index=True)
    target = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "admin_audit_log"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_id}"
