"""
Custom user model.

Identity only — rich profile data (avatar, bio, social links, presence) lives
in a dedicated Profile model added in the profiles phase, so this table stays
narrow and hot-path lookups (auth) touch few columns.

Key decisions:
  * UUID primary key (see apps.common.models.UUIDModel rationale).
  * Email is the login identifier (USERNAME_FIELD); ``username`` is the public
    @handle and is independently unique.
  * Account deletion is soft (is_active=False + deleted_at) so message history
    and references survive; a scrubbing job can anonymise PII later.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel

from .managers import UserManager

username_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9_]{3,32}$",
    message=_(
        "Username must be 3–32 characters and contain only letters, numbers, and underscores."
    ),
)


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
        error_messages={"unique": _("An account with this email already exists.")},
    )
    username = models.CharField(
        _("username"),
        max_length=32,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": _("This username is already taken.")},
    )
    display_name = models.CharField(_("display name"), max_length=80, blank=True)

    # Account state.
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive accounts cannot authenticate."),
    )
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_email_verified = models.BooleanField(_("email verified"), default=False)
    is_verified = models.BooleanField(
        _("verified badge"),
        default=False,
        help_text=_("Official verified account (blue check)."),
    )

    last_seen_at = models.DateTimeField(_("last seen"), null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  # prompted by createsuperuser

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["is_active", "is_email_verified"]),
        ]

    def __str__(self) -> str:
        return f"@{self.username} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    def soft_delete(self) -> None:
        """Deactivate and tombstone the account without destroying rows."""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])

    def mark_seen(self) -> None:
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])

    @property
    def short_name(self) -> str:
        return self.display_name or self.username


class TokenPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "email_verification", _("Email verification")
    PASSWORD_RESET = "password_reset", _("Password reset")


class OneTimeToken(UUIDModel, TimeStampedModel):
    """
    Single-use, hashed, expiring token for email verification and password reset.

    Only a SHA-256 hash of the token is stored — the raw token is delivered to the
    user (in an email link) and never persisted — so a database leak cannot yield
    usable tokens. Issuing a new token for a purpose invalidates the user's older
    unconsumed tokens of that purpose.
    """

    DEFAULT_TTL = {
        TokenPurpose.EMAIL_VERIFICATION: timedelta(days=2),
        TokenPurpose.PASSWORD_RESET: timedelta(hours=1),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="one_time_tokens",
    )
    purpose = models.CharField(max_length=32, choices=TokenPurpose.choices, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        db_table = "accounts_one_time_token"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose"])]

    def __str__(self) -> str:
        return f"{self.get_purpose_display()} for {self.user_id}"

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user, purpose: str, ttl: timedelta | None = None) -> tuple[OneTimeToken, str]:
        """Create a fresh token, invalidating the user's prior ones of this purpose.

        Returns ``(instance, raw_token)`` — the raw token must be emailed, not stored.
        """
        cls.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(
            consumed_at=timezone.now()
        )
        raw = secrets.token_urlsafe(48)
        ttl = ttl or cls.DEFAULT_TTL.get(purpose, timedelta(hours=24))
        token = cls.objects.create(
            user=user,
            purpose=purpose,
            token_hash=cls.hash_token(raw),
            expires_at=timezone.now() + ttl,
        )
        return token, raw

    @classmethod
    def verify(cls, raw: str, purpose: str) -> OneTimeToken | None:
        """Return a valid, unconsumed token matching the raw value, else None."""
        try:
            token = cls.objects.get(token_hash=cls.hash_token(raw), purpose=purpose)
        except cls.DoesNotExist:
            return None
        return token if token.is_valid else None

    @property
    def is_valid(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def consume(self) -> None:
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at", "updated_at"])


class UserSession(UUIDModel, TimeStampedModel):
    """
    A login session on a single device.

    The session id is embedded as the ``sid`` claim in issued JWTs, so a session
    survives refresh-token rotation and can be revoked server-side independently of
    token expiry (immediate revocation is enforced via a Redis flag checked by the
    authentication class). Powers the "active devices / sessions" UI.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    device_label = models.CharField(max_length=120, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        db_table = "accounts_user_session"
        ordering = ["-last_used_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Session {self.id} ({self.device_label or 'unknown device'})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def touch(self, ip: str | None = None) -> None:
        self.last_used_at = timezone.now()
        fields = ["last_used_at"]
        if ip and ip != self.ip_address:
            self.ip_address = ip
            fields.append("ip_address")
        self.save(update_fields=fields)

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])


class SecurityEventType(models.TextChoices):
    REGISTERED = "registered", _("Registered")
    EMAIL_VERIFIED = "email_verified", _("Email verified")
    LOGIN = "login", _("Login")
    LOGIN_FAILED = "login_failed", _("Login failed")
    LOGOUT = "logout", _("Logout")
    TOKEN_REFRESHED = "token_refreshed", _("Token refreshed")
    PASSWORD_CHANGED = "password_changed", _("Password changed")
    PASSWORD_RESET_REQUESTED = "password_reset_requested", _("Password reset requested")
    PASSWORD_RESET_COMPLETED = "password_reset_completed", _("Password reset completed")
    SESSION_REVOKED = "session_revoked", _("Session revoked")


class SecurityEvent(UUIDModel, TimeStampedModel):
    """
    Append-only audit trail of security-relevant actions (login history, password
    changes, etc.). Surfaced to users as their "security log" and to admins for
    suspicious-activity review. ``user`` is nullable so failed logins against an
    unknown email can still be recorded.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    event_type = models.CharField(max_length=40, choices=SecurityEventType.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "accounts_security_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "event_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} ({self.user_id or 'anon'})"
