"""
Group tests: creation + default channel, invites, public join, channels, roles/
permissions, kick/leave, and channel messaging reusing the chat layer.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.groups.models import Channel, Group, GroupMembership, GroupRole
from apps.groups.services import GroupService

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def owner():
    return make_user("owner")


@pytest.fixture
def member():
    return make_user("member")


@pytest.fixture
def group(owner):
    return GroupService.create_group(owner=owner, name="My Community", is_public=True)


# --------------------------------------------------------------------- creation
def test_create_group_via_api_adds_owner_and_default_channel(owner):
    resp = client_for(owner).post(reverse("v1:groups:list"), {"name": "Cool Group"}, format="json")
    assert resp.status_code == 201
    assert resp.data["my_role"] == GroupRole.OWNER
    group = Group.objects.get(id=resp.data["id"])
    assert GroupMembership.objects.filter(group=group, user=owner, role="owner").exists()
    # Default "general" channel exists with a backing conversation.
    channels = group.channels.all()
    assert [c.name for c in channels] == ["general"]
    assert channels[0].conversation is not None
    assert len(resp.data["channels"]) == 1


def test_my_groups_list(owner, group):
    resp = client_for(owner).get(reverse("v1:groups:list"))
    assert any(g["slug"] == group.slug for g in resp.data)


# ----------------------------------------------------------------------- joining
def test_join_via_invite(owner, member, group):
    invite = GroupService.create_invite(actor=owner, group=group)
    resp = client_for(member).post(
        reverse("v1:groups:join-invite"), {"code": invite.code}, format="json"
    )
    assert resp.status_code == 200
    assert GroupService.membership(group, member) is not None
    invite.refresh_from_db()
    assert invite.uses == 1


def test_invalid_invite_rejected(member, group):
    resp = client_for(member).post(
        reverse("v1:groups:join-invite"), {"code": "nope"}, format="json"
    )
    assert resp.status_code == 400


def test_join_public_group(owner, member, group):
    resp = client_for(member).post(reverse("v1:groups:join-public", args=[group.slug]))
    assert resp.status_code == 200
    assert GroupService.membership(group, member) is not None


def test_cannot_join_private_group_publicly(owner, member):
    private = GroupService.create_group(owner=owner, name="Secret", is_public=False)
    resp = client_for(member).post(reverse("v1:groups:join-public", args=[private.slug]))
    assert resp.status_code == 403


# ----------------------------------------------------------------------- channels
def test_admin_can_create_channel_member_cannot(owner, member, group):
    GroupService.add_member(group=group, user=member)
    # Member (default role) cannot create channels.
    resp = client_for(member).post(
        reverse("v1:groups:channels", args=[group.slug]),
        {"name": "random", "type": "text"},
        format="json",
    )
    assert resp.status_code == 403
    # Owner can.
    resp = client_for(owner).post(
        reverse("v1:groups:channels", args=[group.slug]),
        {"name": "random", "type": "text"},
        format="json",
    )
    assert resp.status_code == 201
    channel = Channel.objects.get(id=resp.data["id"])
    # All current members are participants in the new public channel.
    assert channel.conversation.participants.count() == group.member_count


# -------------------------------------------------------------- roles & removal
def test_change_role_and_rank_guard(owner, member, group):
    GroupService.add_member(group=group, user=member)
    url = reverse("v1:groups:member", args=[group.slug, member.id])
    # Owner promotes member to admin.
    resp = client_for(owner).patch(url, {"role": "admin"}, format="json")
    assert resp.status_code == 200
    assert resp.data["role"] == "admin"

    # An admin cannot promote someone to owner (not an allowed choice) nor above self.
    third = make_user("third")
    GroupService.add_member(group=group, user=third)
    resp = client_for(member).patch(
        reverse("v1:groups:member", args=[group.slug, third.id]),
        {"role": "admin"},  # equal to actor's rank -> denied
        format="json",
    )
    assert resp.status_code == 403


def test_kick_member_and_owner_protected(owner, member, group):
    GroupService.add_member(group=group, user=member)
    # Owner kicks member.
    resp = client_for(owner).delete(reverse("v1:groups:member", args=[group.slug, member.id]))
    assert resp.status_code == 204
    assert GroupService.membership(group, member) is None
    # Nobody can kick the owner.
    GroupService.add_member(group=group, user=member, role=GroupRole.ADMIN)
    resp = client_for(member).delete(reverse("v1:groups:member", args=[group.slug, owner.id]))
    assert resp.status_code in (403, 400)


def test_leave_group_and_owner_cannot_leave(owner, member, group):
    GroupService.add_member(group=group, user=member)
    assert client_for(member).post(reverse("v1:groups:leave", args=[group.slug])).status_code == 204
    assert GroupService.membership(group, member) is None
    # Owner cannot just leave.
    assert client_for(owner).post(reverse("v1:groups:leave", args=[group.slug])).status_code == 403


# --------------------------------------------------- channel messaging (reuse)
def test_channel_messaging_reuses_chat_layer(owner, member, group):
    GroupService.add_member(group=group, user=member)
    channel = group.channels.first()
    conv_id = str(channel.conversation_id)
    msg_url = reverse("v1:chat:message-list", args=[conv_id])

    # Owner posts to the channel; member (a participant) reads it.
    send = client_for(owner).post(msg_url, {"text": "welcome to the channel"}, format="json")
    assert send.status_code == 201
    history = client_for(member).get(msg_url)
    assert [m["text"] for m in history.data["results"]] == ["welcome to the channel"]


def test_non_member_cannot_post_to_channel(owner, group):
    outsider = make_user("outsider")
    channel = group.channels.first()
    resp = client_for(outsider).post(
        reverse("v1:chat:message-list", args=[str(channel.conversation_id)]),
        {"text": "intruder"},
        format="json",
    )
    assert resp.status_code in (403, 404)
