"""Celery task to post-process an uploaded media file."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=15, ignore_result=True)
def process_media_task(self, media_id: str) -> None:
    from .models import MediaFile
    from .processing import process_media

    media = MediaFile.objects.filter(pk=media_id).first()
    if media is None:
        logger.warning("process_media: media %s not found", media_id)
        return
    try:
        process_media(media)
    except Exception as exc:  # pragma: no cover - retried path
        logger.exception("process_media failed for %s", media_id)
        raise self.retry(exc=exc) from exc
