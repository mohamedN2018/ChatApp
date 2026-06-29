"""
Ensure the Celery app is loaded when Django starts so shared_task decorators
register against it. Importing here (rather than in each app) keeps the app a
single well-known instance.
"""

from __future__ import annotations

from .celery import app as celery_app

__all__ = ("celery_app",)
