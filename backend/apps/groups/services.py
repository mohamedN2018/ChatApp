"""
Group/channel service layer.

Membership and channel access are kept consistent with the chat layer: joining a
group adds the user as a ``ConversationParticipant`` in every public channel, so
the existing message endpoints, permission checks, and WebSocket fan-out work for
channels with no special-casing. Leaving marks those participants as departed.
"""

from __future__ import annotations

import secrets

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.chat.models import Conversation, ConversationParticipant, ConversationType

from .models import (
    ROLE_RANK,
    Channel,
    ChannelType,
    Group,
    GroupInvite,
    GroupMembership,
    GroupRole,
)


class GroupService:
    # ------------------------------------------------------------------ helpers
    @staticmethod
    def membership(group: Group, user) -> GroupMembership | None:
        return GroupMembership.objects.filter(group=group, user=user).first()

    @classmethod
    def _require(cls, group: Group, user, min_role: str) -> GroupMembership:
        m = cls.membership(group, user)
        if m is None or m.rank < ROLE_RANK[min_role]:
            raise PermissionDenied("You don't have permission to do that in this group.")
        return m

    @staticmethod
    def _unique_slug(name: str) -> str:
        base = slugify(name)[:120] or "group"
        slug = base
        while Group.objects.filter(slug=slug).exists():
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug

    # --------------------------------------------------------------- group CRUD
    @classmethod
    @transaction.atomic
    def create_group(
        cls, *, owner, name, description="", is_public=False, max_members=None
    ) -> Group:
        group = Group.objects.create(
            name=name,
            slug=cls._unique_slug(name),
            description=description,
            is_public=is_public,
            max_members=max_members,
            owner=owner,
        )
        GroupMembership.objects.create(group=group, user=owner, role=GroupRole.OWNER)
        # Every group starts with a default text channel.
        cls.create_channel(actor=owner, group=group, name="general", channel_type=ChannelType.TEXT)
        return group

    @classmethod
    def delete_group(cls, *, actor, group) -> None:
        if group.owner_id != actor.id:
            raise PermissionDenied("Only the owner can delete the group.")
        group.delete()  # soft delete (BaseModel)

    # ------------------------------------------------------------------ channels
    @classmethod
    @transaction.atomic
    def create_channel(
        cls, *, actor, group, name, channel_type=ChannelType.TEXT, topic="", is_private=False
    ) -> Channel:
        cls._require(group, actor, GroupRole.ADMIN)
        conversation = Conversation.objects.create(type=ConversationType.GROUP)
        channel = Channel.objects.create(
            group=group,
            conversation=conversation,
            name=name,
            type=channel_type,
            topic=topic,
            is_private=is_private,
            is_readonly=channel_type == ChannelType.ANNOUNCEMENT,
            position=group.channels.count(),
        )
        # Public channel: every current member becomes a participant.
        if not is_private:
            members = group.memberships.values_list("user_id", flat=True)
            cls._bulk_add_participants(conversation, members)
        else:
            cls._bulk_add_participants(conversation, [actor.id])
        return channel

    @classmethod
    def delete_channel(cls, *, actor, channel) -> None:
        cls._require(channel.group, actor, GroupRole.ADMIN)
        channel.delete()

    @staticmethod
    def _bulk_add_participants(conversation, user_ids) -> None:
        existing = set(
            ConversationParticipant.objects.filter(conversation=conversation).values_list(
                "user_id", flat=True
            )
        )
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, user_id=uid)
                for uid in user_ids
                if uid not in existing
            ]
        )

    # ------------------------------------------------------------------ members
    @classmethod
    @transaction.atomic
    def add_member(cls, *, group, user, role=GroupRole.MEMBER) -> GroupMembership:
        if cls.membership(group, user) is not None:
            raise ValidationError("Already a member of this group.")
        if group.max_members is not None and group.member_count >= group.max_members:
            raise ValidationError("This group is full.")
        membership = GroupMembership.objects.create(group=group, user=user, role=role)
        # Add the new member to all public channels.
        for channel in group.channels.filter(is_private=False).select_related("conversation"):
            cls._bulk_add_participants(channel.conversation, [user.id])
        return membership

    @classmethod
    @transaction.atomic
    def remove_member(cls, *, actor, group, target_user) -> None:
        actor_m = cls._require(group, actor, GroupRole.MODERATOR)
        target_m = cls.membership(group, target_user)
        if target_m is None:
            raise ValidationError("That user is not a member.")
        if target_m.role == GroupRole.OWNER:
            raise PermissionDenied("The owner cannot be removed.")
        if target_m.rank >= actor_m.rank and actor.id != target_user.id:
            raise PermissionDenied("You cannot remove a member with an equal or higher role.")
        cls._detach_member(group, target_user)
        target_m.delete()

    @classmethod
    def leave_group(cls, *, user, group) -> None:
        membership = cls.membership(group, user)
        if membership is None:
            raise ValidationError("You are not a member.")
        if membership.role == GroupRole.OWNER:
            raise PermissionDenied("The owner must transfer ownership or delete the group.")
        cls._detach_member(group, user)
        membership.delete()

    @staticmethod
    def _detach_member(group, user) -> None:
        ConversationParticipant.objects.filter(
            conversation__channel__group=group, user=user, left_at__isnull=True
        ).update(left_at=timezone.now())

    @classmethod
    def change_role(cls, *, actor, group, target_user, role) -> GroupMembership:
        actor_m = cls._require(group, actor, GroupRole.ADMIN)
        target_m = cls.membership(group, target_user)
        if target_m is None:
            raise ValidationError("That user is not a member.")
        if target_m.role == GroupRole.OWNER:
            raise PermissionDenied("The owner's role cannot be changed here.")
        if ROLE_RANK[role] >= actor_m.rank or target_m.rank >= actor_m.rank:
            raise PermissionDenied("You cannot assign a role at or above your own.")
        target_m.role = role
        target_m.save(update_fields=["role", "updated_at"])
        return target_m

    @classmethod
    @transaction.atomic
    def transfer_ownership(cls, *, actor, group, target_user) -> None:
        if group.owner_id != actor.id:
            raise PermissionDenied("Only the owner can transfer ownership.")
        target_m = cls.membership(group, target_user)
        if target_m is None:
            raise ValidationError("That user is not a member.")
        actor_m = cls.membership(group, actor)
        target_m.role = GroupRole.OWNER
        actor_m.role = GroupRole.ADMIN
        target_m.save(update_fields=["role", "updated_at"])
        actor_m.save(update_fields=["role", "updated_at"])
        group.owner = target_user
        group.save(update_fields=["owner", "updated_at"])

    # ------------------------------------------------------------------ invites
    @classmethod
    def create_invite(cls, *, actor, group, expires_in=None, max_uses=None) -> GroupInvite:
        cls._require(group, actor, GroupRole.MODERATOR)
        expires_at = None
        if expires_in:
            expires_at = timezone.now() + expires_in
        elif expires_in is None:
            expires_at = timezone.now() + GroupInvite.DEFAULT_TTL
        return GroupInvite.objects.create(
            group=group,
            code=secrets.token_urlsafe(8)[:12],
            created_by=actor,
            expires_at=expires_at,
            max_uses=max_uses,
        )

    @classmethod
    @transaction.atomic
    def join_via_invite(cls, *, user, code) -> Group:
        invite = GroupInvite.objects.select_for_update().filter(code=code).first()
        if invite is None or not invite.is_valid:
            raise ValidationError("This invite is invalid or has expired.")
        group = invite.group
        if cls.membership(group, user) is None:
            cls.add_member(group=group, user=user)
            invite.uses += 1
            invite.save(update_fields=["uses", "updated_at"])
        return group

    @classmethod
    def join_public(cls, *, user, group) -> GroupMembership:
        if not group.is_public:
            raise PermissionDenied("This group is invite-only.")
        existing = cls.membership(group, user)
        return existing or cls.add_member(group=group, user=user)
