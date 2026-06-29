"""
Social graph service layer.

Encapsulates every mutation and invariant of the social graph: privacy gating,
block checks, mutual-request auto-accept, and the cascading side effects of a
block (sever follows/friendship/pending requests). Views stay thin.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.profiles.models import Visibility

from .models import Block, Follow, FriendRequest, FriendRequestStatus, Friendship, Mute


class SocialService:
    # ----------------------------------------------------------- relationship state
    @staticmethod
    def is_blocked_between(a, b) -> bool:
        return Block.objects.filter(Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)).exists()

    @staticmethod
    def are_friends(a, b) -> bool:
        low, high = Friendship.order(a, b)
        return Friendship.objects.filter(user_low=low, user_high=high).exists()

    @staticmethod
    def is_following(a, b) -> bool:
        return Follow.objects.filter(follower=a, following=b).exists()

    # ----------------------------------------------------------------- privacy gate
    @classmethod
    def _check_visibility(cls, actor, target, setting_value: str, action: str) -> None:
        if setting_value == Visibility.NOBODY:
            raise PermissionDenied(f"This user does not allow {action}.")
        if setting_value == Visibility.FRIENDS and not cls.are_friends(actor, target):
            raise PermissionDenied(f"Only friends can {action} this user.")

    @staticmethod
    def _guard_not_self(actor, target, verb: str) -> None:
        if actor == target:
            raise ValidationError(f"You cannot {verb} yourself.")

    # ------------------------------------------------------------------------ follow
    @classmethod
    def follow(cls, *, actor, target):
        cls._guard_not_self(actor, target, "follow")
        if cls.is_blocked_between(actor, target):
            raise PermissionDenied("This action is not allowed.")
        cls._check_visibility(actor, target, target.privacy.who_can_follow, "follow")
        follow, _ = Follow.objects.get_or_create(follower=actor, following=target)
        return follow

    @classmethod
    def unfollow(cls, *, actor, target) -> None:
        Follow.objects.filter(follower=actor, following=target).delete()

    # ---------------------------------------------------------------- friend requests
    @classmethod
    @transaction.atomic
    def send_friend_request(cls, *, actor, target):
        cls._guard_not_self(actor, target, "friend")
        if cls.is_blocked_between(actor, target):
            raise PermissionDenied("This action is not allowed.")
        if cls.are_friends(actor, target):
            raise ValidationError("You are already friends.")
        # If they've already requested us, sending back accepts it (mutual).
        reverse = FriendRequest.objects.filter(
            from_user=target, to_user=actor, status=FriendRequestStatus.PENDING
        ).first()
        if reverse is not None:
            return cls._accept(reverse)
        existing = FriendRequest.objects.filter(
            from_user=actor, to_user=target, status=FriendRequestStatus.PENDING
        ).first()
        if existing is not None:
            return existing
        cls._check_visibility(
            actor, target, target.privacy.who_can_friend_request, "friend request"
        )
        return FriendRequest.objects.create(from_user=actor, to_user=target)

    @classmethod
    @transaction.atomic
    def _accept(cls, request: FriendRequest) -> FriendRequest:
        request.mark(FriendRequestStatus.ACCEPTED)
        low, high = Friendship.order(request.from_user, request.to_user)
        Friendship.objects.get_or_create(user_low=low, user_high=high)
        return request

    @classmethod
    def accept_friend_request(cls, *, actor, request: FriendRequest) -> FriendRequest:
        if request.to_user_id != actor.id:
            raise PermissionDenied("You can only accept requests sent to you.")
        if request.status != FriendRequestStatus.PENDING:
            raise ValidationError("This request is no longer pending.")
        return cls._accept(request)

    @classmethod
    def reject_friend_request(cls, *, actor, request: FriendRequest) -> FriendRequest:
        if request.to_user_id != actor.id:
            raise PermissionDenied("You can only reject requests sent to you.")
        if request.status != FriendRequestStatus.PENDING:
            raise ValidationError("This request is no longer pending.")
        request.mark(FriendRequestStatus.REJECTED)
        return request

    @classmethod
    def cancel_friend_request(cls, *, actor, request: FriendRequest) -> FriendRequest:
        if request.from_user_id != actor.id:
            raise PermissionDenied("You can only cancel requests you sent.")
        if request.status != FriendRequestStatus.PENDING:
            raise ValidationError("This request is no longer pending.")
        request.mark(FriendRequestStatus.CANCELLED)
        return request

    @classmethod
    def remove_friend(cls, *, actor, target) -> None:
        low, high = Friendship.order(actor, target)
        Friendship.objects.filter(user_low=low, user_high=high).delete()

    # ------------------------------------------------------------------------- block
    @classmethod
    @transaction.atomic
    def block(cls, *, actor, target):
        cls._guard_not_self(actor, target, "block")
        block, _ = Block.objects.get_or_create(blocker=actor, blocked=target)
        # Blocking severs all existing ties in both directions.
        Follow.objects.filter(
            Q(follower=actor, following=target) | Q(follower=target, following=actor)
        ).delete()
        low, high = Friendship.order(actor, target)
        Friendship.objects.filter(user_low=low, user_high=high).delete()
        FriendRequest.objects.filter(
            Q(from_user=actor, to_user=target) | Q(from_user=target, to_user=actor),
            status=FriendRequestStatus.PENDING,
        ).update(status=FriendRequestStatus.CANCELLED, responded_at=timezone.now())
        return block

    @classmethod
    def unblock(cls, *, actor, target) -> None:
        Block.objects.filter(blocker=actor, blocked=target).delete()

    # -------------------------------------------------------------------------- mute
    @classmethod
    def mute(cls, *, actor, target, until=None):
        cls._guard_not_self(actor, target, "mute")
        mute, _ = Mute.objects.update_or_create(
            muter=actor, muted=target, defaults={"until": until}
        )
        return mute

    @classmethod
    def unmute(cls, *, actor, target) -> None:
        Mute.objects.filter(muter=actor, muted=target).delete()
