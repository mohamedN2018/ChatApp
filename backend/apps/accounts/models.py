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
