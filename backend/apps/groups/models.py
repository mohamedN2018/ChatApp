"""
Groups (communities/servers) and their channels.

A Group has members with roles and one or more Channels. Each Channel is backed
by a chat ``Conversation`` (type "group"), so all existing chat machinery —
messages, reactions, receipts, attachments, and the WebSocket broadcast — works
for channels unchanged. Group membership is mirrored into each channel's
``ConversationParticipant`` rows (by the service) so messaging permissions and
realtime fan-out reuse the chat layer.

Role hierarchy (high -> low): owner > admin > moderator > member > guest.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


def group_avatar_to(instance: Group, filename: str) -> str:
    return f"groups/{instance.id}/avatar_{filename}"


def group_banner_to(instance: Group, filename: str) -> str:
    return f"groups/{instance.id}/banner_{filename}"


class GroupRole(models.TextChoices):
    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    MODERATOR = "moderator", _("Moderator")
    MEMBER = "member", _("Member")
    GUEST = "guest", _("Guest")


# Higher number = more privileged. Used for permission comparisons.
ROLE_RANK = {
    GroupRole.GUEST: 0,
    GroupRole.MEMBER: 1,
    GroupRole.MODERATOR: 2,
    GroupRole.ADMIN: 3,
    GroupRole.OWNER: 4,
}


class ChannelType(models.TextChoices):
    TEXT = "text", _("Text")
    VOICE = "voice", _("Voice")
    VIDEO = "video", _("Video")
    ANNOUNCEMENT = "announcement", _("Announcement")


class Group(BaseModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to=group_avatar_to, null=True, blank=True)
    banner = models.ImageField(upload_to=group_banner_to, null=True, blank=True)
    owner = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="owned_groups")
    is_public = models.BooleanField(default=False)
    max_members = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited")

    class Meta:
        db_table = "groups_group"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_public"])]

    def __str__(self) -> str:
        return f"Group<{self.slug}>"

    @property
    def member_count(self) -> int:
        return self.memberships.count()


class GroupMembership(UUIDModel, TimeStampedModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=10, choices=GroupRole.choices, default=GroupRole.MEMBER)
    nickname = models.CharField(max_length=80, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "groups_membership"
        constraints = [models.UniqueConstraint(fields=["group", "user"], name="uniq_group_member")]
        indexes = [models.Index(fields=["user"]), models.Index(fields=["group", "role"])]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.group_id} ({self.role})"

    @property
    def rank(self) -> int:
        return ROLE_RANK.get(self.role, 0)


class Channel(BaseModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="channels")
    conversation = models.OneToOneField(
        "chat.Conversation", on_delete=models.CASCADE, related_name="channel"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=12, choices=ChannelType.choices, default=ChannelType.TEXT)
    topic = models.CharField(max_length=255, blank=True)
    is_private = models.BooleanField(default=False)
    is_readonly = models.BooleanField(
        default=False, help_text="Announcement channels: only admins post."
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "groups_channel"
        ordering = ["position", "created_at"]
        indexes = [models.Index(fields=["group", "position"])]

    def __str__(self) -> str:
        return f"#{self.name} ({self.group_id})"


class GroupInvite(UUIDModel, TimeStampedModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invites")
    code = models.CharField(max_length=20, unique=True, db_index=True)
    created_by = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, related_name="created_invites"
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    DEFAULT_TTL = timedelta(days=7)

    class Meta:
        db_table = "groups_invite"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite<{self.code}>"

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return self.max_uses is None or self.uses < self.max_uses
