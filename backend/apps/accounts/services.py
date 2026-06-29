"""
Authentication service layer.

All auth business logic lives here so views/serializers stay thin and the rules
are unit-testable without HTTP. Session lifecycle is the single source of truth
for "is this login still valid":

  * Access tokens are rejected the instant a session is revoked, via a Redis flag
    (``mark_session_revoked``) checked by ``SessionAwareJWTAuthentication``.
  * Refresh is rejected when the backing ``UserSession`` is inactive (checked by
    the refresh serializer). Together these revoke a device immediately, without
    relying on token expiry, and without per-user token-blacklist scans.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from . import tasks
from .models import (
    OneTimeToken,
    SecurityEvent,
    SecurityEventType,
    TokenPurpose,
    UserSession,
)
from .tokens import build_tokens_for_session, mark_session_revoked

User = get_user_model()


@dataclass(frozen=True)
class RequestContext:
    """Carrier for request metadata so the service stays decoupled from HTTP."""

    ip: str | None = None
    user_agent: str = ""
    device_label: str = ""


class AuthService:
    # ------------------------------------------------------------------ events
    @staticmethod
    def log_event(event_type: str, *, user=None, ctx: RequestContext | None = None, **metadata):
        return SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            ip_address=ctx.ip if ctx else None,
            user_agent=ctx.user_agent if ctx else "",
            metadata=metadata or {},
        )

    # ----------------------------------------------- registration & verification
    @classmethod
    @transaction.atomic
    def register(cls, *, email, username, password, display_name="", ctx=None):
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            display_name=display_name,
        )
        cls._issue_verification(user)
        cls.log_event(SecurityEventType.REGISTERED, user=user, ctx=ctx)
        return user

    @staticmethod
    def _issue_verification(user) -> None:
        _, raw = OneTimeToken.issue(user, TokenPurpose.EMAIL_VERIFICATION)
        tasks.send_verification_email_task.delay(str(user.pk), raw)

    @classmethod
    def resend_verification(cls, *, email) -> None:
        """Idempotent and privacy-preserving: never reveals if the email exists."""
        user = User.objects.filter(email=email.lower().strip()).first()
        if user and not user.is_email_verified:
            cls._issue_verification(user)

    @classmethod
    @transaction.atomic
    def verify_email(cls, *, raw_token, ctx=None):
        token = OneTimeToken.verify(raw_token, TokenPurpose.EMAIL_VERIFICATION)
        if token is None:
            return None
        token.consume()
        user = token.user
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified", "updated_at"])
            cls.log_event(SecurityEventType.EMAIL_VERIFIED, user=user, ctx=ctx)
        return user

    # ------------------------------------------------------------- login/logout
    @classmethod
    @transaction.atomic
    def login(cls, *, user, ctx: RequestContext | None = None):
        session = UserSession.objects.create(
            user=user,
            device_label=ctx.device_label if ctx else "",
            user_agent=ctx.user_agent if ctx else "",
            ip_address=ctx.ip if ctx else None,
            expires_at=timezone.now() + api_settings.REFRESH_TOKEN_LIFETIME,
        )
        access, refresh = build_tokens_for_session(session)
        user.mark_seen()
        cls.log_event(SecurityEventType.LOGIN, user=user, ctx=ctx, session_id=str(session.id))
        tasks.send_login_alert_email_task.delay(
            str(user.pk),
            ip=ctx.ip if ctx else None,
            user_agent=ctx.user_agent if ctx else "",
            when=timezone.now().strftime("%Y-%m-%d %H:%M UTC"),
        )
        return access, refresh, session

    @classmethod
    @transaction.atomic
    def logout(cls, *, user, refresh_token, ctx=None):
        sid = None
        try:
            token = RefreshToken(refresh_token)
            sid = token.get("sid")
            token.blacklist()  # immediate refresh invalidation (defence in depth)
        except TokenError:
            pass
        if sid:
            cls._revoke_session_obj(UserSession.objects.filter(pk=sid, user=user).first(), sid)
        cls.log_event(
            SecurityEventType.LOGOUT, user=user, ctx=ctx, session_id=str(sid) if sid else None
        )

    # ----------------------------------------------------------------- sessions
    @staticmethod
    def _revoke_session_obj(session: UserSession | None, sid) -> None:
        if session is not None:
            session.revoke()
        mark_session_revoked(str(sid))

    @classmethod
    def revoke_session(cls, *, user, session_id, ctx=None) -> bool:
        session = UserSession.objects.filter(pk=session_id, user=user).first()
        if session is None:
            return False
        cls._revoke_session_obj(session, session_id)
        cls.log_event(
            SecurityEventType.SESSION_REVOKED, user=user, ctx=ctx, session_id=str(session_id)
        )
        return True

    @classmethod
    def revoke_all_sessions(cls, *, user, exclude_session_id=None) -> int:
        sessions = UserSession.objects.filter(user=user, revoked_at__isnull=True)
        if exclude_session_id:
            sessions = sessions.exclude(pk=exclude_session_id)
        count = 0
        for session in sessions:
            cls._revoke_session_obj(session, session.id)
            count += 1
        return count

    # -------------------------------------------------------- password recovery
    @classmethod
    def request_password_reset(cls, *, email, ctx=None) -> None:
        """Idempotent; response is identical whether or not the email exists."""
        user = User.objects.filter(email=email.lower().strip(), is_active=True).first()
        if user:
            _, raw = OneTimeToken.issue(user, TokenPurpose.PASSWORD_RESET)
            tasks.send_password_reset_email_task.delay(str(user.pk), raw)
            cls.log_event(SecurityEventType.PASSWORD_RESET_REQUESTED, user=user, ctx=ctx)

    @classmethod
    @transaction.atomic
    def reset_password(cls, *, raw_token, new_password, ctx=None):
        token = OneTimeToken.verify(raw_token, TokenPurpose.PASSWORD_RESET)
        if token is None:
            return None
        token.consume()
        user = token.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        # Security: a reset signs the account out of every device.
        cls.revoke_all_sessions(user=user)
        cls.log_event(SecurityEventType.PASSWORD_RESET_COMPLETED, user=user, ctx=ctx)
        return user

    @classmethod
    @transaction.atomic
    def change_password(cls, *, user, new_password, current_session_id=None, ctx=None):
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        # Sign out other devices but keep the current session alive.
        cls.revoke_all_sessions(user=user, exclude_session_id=current_session_id)
        cls.log_event(SecurityEventType.PASSWORD_CHANGED, user=user, ctx=ctx)
