"""Celery application bootstrap.

Reads configuration from Django settings (the ``CELERY_`` namespace) and
autodiscovers ``tasks.py`` modules across installed apps.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("chatapp")
# All Celery config lives in Django settings under the CELERY_ prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - operational helper
    """Trivial task to confirm the worker is wired up: ``debug_task.delay()``."""
    print(f"Celery request: {self.request!r}")
