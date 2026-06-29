"""
Celery tasks for transactional email.

Kept thin: each task resolves the user and delegates to the pure send functions in
``emails.py``. Retried with backoff on transient SMTP failures. Email sending is
offloaded so it never blocks an API request or a WebSocket frame.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from . import emails

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_verification_email_task(self, user_id: str, raw_token: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Verification email skipped: user %s not found", user_id)
        return
    try:
        emails.send_verification_email(user, raw_token)
    except Exception as exc:  # pragma: no cover - retried path
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_password_reset_email_task(self, user_id: str, raw_token: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Reset email skipped: user %s not found", user_id)
        return
    try:
        emails.send_password_reset_email(user, raw_token)
    except Exception as exc:  # pragma: no cover - retried path
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_login_alert_email_task(
    self, user_id: str, *, ip: str | None, user_agent: str, when: str
) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    try:
        emails.send_login_alert_email(user, ip=ip, user_agent=user_agent, when=when)
    except Exception as exc:  # pragma: no cover - retried path
        raise self.retry(exc=exc) from exc
