"""
Transactional email rendering and delivery.

Pure functions (no Celery here) so they're trivially unit-testable with the
locmem email backend. The Celery tasks in ``tasks.py`` call these. Each email has
a plain-text and an HTML part.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

APP_NAME = "ChatApp"


def _send(subject: str, to_email: str, template_base: str, context: dict) -> None:
    context = {"app_name": APP_NAME, **context}
    text_body = render_to_string(f"emails/{template_base}.txt", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    try:
        html_body = render_to_string(f"emails/{template_base}.html", context)
        msg.attach_alternative(html_body, "text/html")
    except Exception:
        # HTML part is optional; fall back to text-only if the template is absent.
        pass
    msg.send()


def _frontend_url(path: str, **params: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    query = f"?{urlencode(params)}" if params else ""
    return f"{base}{path}{query}"


def send_verification_email(user, raw_token: str) -> None:
    _send(
        subject=f"Confirm your {APP_NAME} email",
        to_email=user.email,
        template_base="verification",
        context={
            "name": user.short_name,
            "action_url": _frontend_url("/verify-email", token=raw_token),
            "expires_hours": 48,
        },
    )


def send_password_reset_email(user, raw_token: str) -> None:
    _send(
        subject=f"Reset your {APP_NAME} password",
        to_email=user.email,
        template_base="password_reset",
        context={
            "name": user.short_name,
            "action_url": _frontend_url("/reset-password", token=raw_token),
            "expires_hours": 1,
        },
    )


def send_login_alert_email(user, *, ip: str | None, user_agent: str, when: str) -> None:
    _send(
        subject=f"New sign-in to your {APP_NAME} account",
        to_email=user.email,
        template_base="login_alert",
        context={
            "name": user.short_name,
            "ip": ip or "unknown",
            "user_agent": user_agent or "unknown device",
            "when": when,
            "security_url": _frontend_url("/settings/security"),
        },
    )
