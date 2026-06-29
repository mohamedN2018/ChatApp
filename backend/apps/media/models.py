"""
Media domain: uploaded files and resumable upload sessions.

A ``MediaFile`` is an owned, stored blob (in MinIO/S3 via django-storages) plus
extracted metadata (dimensions, duration, waveform) and an optional thumbnail.
Heavy extraction runs asynchronously in Celery, so ``status`` advances
PENDING -> PROCESSING -> READY/FAILED.

``UploadSession`` backs chunked/resumable uploads for large files: chunks are
stored individually and assembled into a MediaFile on completion.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


def media_upload_to(instance: MediaFile, filename: str) -> str:
    return f"media/{instance.owner_id}/{instance.id}/{filename}"


def thumb_upload_to(instance: MediaFile, filename: str) -> str:
    return f"media/{instance.owner_id}/{instance.id}/thumb_{filename}"


class MediaKind(models.TextChoices):
    IMAGE = "image", _("Image")
    VIDEO = "video", _("Video")
    AUDIO = "audio", _("Audio")
    VOICE = "voice", _("Voice note")
    FILE = "file", _("File")


class MediaStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    READY = "ready", _("Ready")
    FAILED = "failed", _("Failed")


class MediaFile(UUIDModel, TimeStampedModel):
    owner = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="media_files")
    file = models.FileField(upload_to=media_upload_to, max_length=500)
    thumbnail = models.FileField(upload_to=thumb_upload_to, max_length=500, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=MediaKind.choices, default=MediaKind.FILE)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150, blank=True)
    size = models.BigIntegerField(default=0)

    # Image/video dimensions; audio/video duration; voice-note waveform peaks.
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Seconds")
    waveform = models.JSONField(null=True, blank=True)

    status = models.CharField(
        max_length=12, choices=MediaStatus.choices, default=MediaStatus.PENDING
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "media_file"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "kind"])]

    def __str__(self) -> str:
        return f"MediaFile<{self.kind}:{self.id}>"

    @staticmethod
    def kind_for_content_type(content_type: str, filename: str = "") -> str:
        ct = (content_type or "").lower()
        if ct.startswith("image/"):
            return MediaKind.IMAGE
        if ct.startswith("video/"):
            return MediaKind.VIDEO
        if ct.startswith("audio/"):
            return MediaKind.AUDIO
        return MediaKind.FILE


class UploadStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    COMPLETED = "completed", _("Completed")
    ABORTED = "aborted", _("Aborted")


class UploadSession(UUIDModel, TimeStampedModel):
    """Tracks a chunked upload in progress. Chunks live under ``chunks/{id}/{i}``
    in storage until assembled."""

    DEFAULT_TTL = timedelta(hours=6)

    owner = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="upload_sessions")
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150, blank=True)
    total_size = models.BigIntegerField()
    total_chunks = models.PositiveIntegerField()
    received_chunks = models.JSONField(default=list)  # indices received so far
    status = models.CharField(
        max_length=10, choices=UploadStatus.choices, default=UploadStatus.PENDING
    )
    expires_at = models.DateTimeField()
    media = models.ForeignKey(
        MediaFile, on_delete=models.SET_NULL, null=True, blank=True, related_name="upload_session"
    )

    class Meta:
        db_table = "media_upload_session"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"UploadSession<{self.id}> {len(self.received_chunks)}/{self.total_chunks}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.DEFAULT_TTL
        super().save(*args, **kwargs)

    @property
    def is_complete(self) -> bool:
        return len(set(self.received_chunks)) >= self.total_chunks

    def chunk_key(self, index: int) -> str:
        return f"chunks/{self.id}/{index}"
