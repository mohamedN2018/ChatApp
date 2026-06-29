"""
Social graph: follows (asymmetric), friendships (symmetric), blocks, mutes.

* Follow      — one-directional (follower -> following), like Twitter/Instagram.
* FriendRequest / Friendship — mutual, request/accept, like Facebook/Discord.
* Block       — hard: hides content and severs follows/friendships both ways.
* Mute        — soft: suppresses notifications without the other party knowing.

Friendship is stored as a single canonical row (user_low, user_high ordered by
id) to avoid duplicate (a,b)/(b,a) pairs.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


class Follow(UUIDModel, TimeStampedModel):
    follower = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="following_set")
    following = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="follower_set")

    class Meta:
        db_table = "social_follow"
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="uniq_follow_pair"),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="follow_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["following"]),
        ]

    def __str__(self) -> str:
        return f"{self.follower_id} -> {self.following_id}"


class FriendRequestStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    REJECTED = "rejected", _("Rejected")
    CANCELLED = "cancelled", _("Cancelled")


class FriendRequest(UUIDModel, TimeStampedModel):
    from_user = models.ForeignKey(
        USER, on_delete=models.CASCADE, related_name="sent_friend_requests"
    )
    to_user = models.ForeignKey(
        USER, on_delete=models.CASCADE, related_name="received_friend_requests"
    )
    status = models.CharField(
        max_length=10, choices=FriendRequestStatus.choices, default=FriendRequestStatus.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "social_friend_request"
        ordering = ["-created_at"]
        constraints = [
            # At most one *pending* request per ordered pair.
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                condition=models.Q(status="pending"),
                name="uniq_pending_friend_request",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_user=models.F("to_user")),
                name="friend_request_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["from_user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.from_user_id} -> {self.to_user_id} ({self.status})"

    def mark(self, status: str) -> None:
        self.status = status
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])


class Friendship(UUIDModel, TimeStampedModel):
    """Symmetric friendship stored canonically (user_low.id < user_high.id)."""

    user_low = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="friendships_low")
    user_high = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="friendships_high")

    class Meta:
        db_table = "social_friendship"
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="uniq_friendship_pair"),
            models.CheckConstraint(
                condition=~models.Q(user_low=models.F("user_high")),
                name="friendship_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["user_low"]),
            models.Index(fields=["user_high"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_low_id} <-> {self.user_high_id}"

    @staticmethod
    def order(user_a, user_b):
        """Return (low, high) ordered by stringified id for canonical storage."""
        return (user_a, user_b) if str(user_a.id) < str(user_b.id) else (user_b, user_a)


class Block(UUIDModel, TimeStampedModel):
    blocker = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="blocking")
    blocked = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="blocked_by")

    class Meta:
        db_table = "social_block"
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_block_pair"),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="block_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["blocker"]),
            models.Index(fields=["blocked"]),
        ]

    def __str__(self) -> str:
        return f"{self.blocker_id} blocked {self.blocked_id}"


class Mute(UUIDModel, TimeStampedModel):
    muter = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="muting")
    muted = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="muted_by")
    until = models.DateTimeField(null=True, blank=True, help_text="Null = indefinite")

    class Meta:
        db_table = "social_mute"
        constraints = [
            models.UniqueConstraint(fields=["muter", "muted"], name="uniq_mute_pair"),
            models.CheckConstraint(
                condition=~models.Q(muter=models.F("muted")),
                name="mute_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.muter_id} muted {self.muted_id}"

    @property
    def is_active(self) -> bool:
        return self.until is None or self.until > timezone.now()
