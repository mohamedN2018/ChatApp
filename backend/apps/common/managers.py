"""
Managers and querysets for soft-deletable models.

Soft delete is implemented as a non-destructive flag (``is_deleted`` +
``deleted_at``). The default manager hides soft-deleted rows so application
code never sees them by accident; ``all_objects`` exposes everything for admin,
audits, and restore flows.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that understands soft deletion."""

    def delete(self):  # type: ignore[override]
        """Bulk soft-delete: mark rows instead of issuing SQL DELETE."""
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently remove rows (irreversible)."""
        return super().delete()

    def restore(self):
        """Un-delete previously soft-deleted rows."""
        return super().update(is_deleted=False, deleted_at=None)

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Default manager: returns only rows that are not soft-deleted."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Escape-hatch manager exposing every row, including soft-deleted ones."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)
