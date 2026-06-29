"""
Abstract base models shared across the platform.

Design choices (apply to nearly every domain table):
  * UUID primary keys — non-enumerable, safe to expose in URLs/APIs, and
    collision-free across shards/replicas (important for horizontal scaling).
  * created_at / updated_at audit timestamps on every row.
  * Soft delete — rows are flagged, never physically removed, so messages and
    user content can be "deleted" while preserving referential integrity and
    audit trails. A periodic Celery job can hard-purge old soft-deleted rows.

Compose ``BaseModel`` for the common case. Use the narrower mixins when a table
needs only some of the behaviour.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from .managers import AllObjectsManager, SoftDeleteManager


class UUIDModel(models.Model):
    """Primary key is a UUIDv4 instead of an auto-increment integer."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Adds self-managing created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "created_at"


class SoftDeleteModel(models.Model):
    """Adds soft-delete semantics and swaps in the soft-delete managers."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    # ``objects`` hides soft-deleted rows; ``all_objects`` sees everything.
    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, hard: bool = False):
        """Soft-delete by default; pass ``hard=True`` to truly remove the row."""
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])
        return None

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """The default base for domain models: UUID PK + timestamps + soft delete."""

    class Meta:
        abstract = True
        ordering = ["-created_at"]
