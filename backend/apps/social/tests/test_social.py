"""Tests for the social graph: follow, friends, block (cascades), mute, lists."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.profiles.models import Visibility
from apps.social.models import Block, Follow, FriendRequest, FriendRequestStatus, Mute
from apps.social.services import SocialService

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


@pytest.fixture
def alice():
    return make_user("alice")


@pytest.fixture
def bob():
    return make_user("bob")


@pytest.fixture
def client_for():
    def _make(user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    return _make


# --------------------------------------------------------------------- follow
def test_follow_and_unfollow(client_for, alice, bob):
    c = client_for(alice)
    resp = c.post(reverse("v1:social:follow", args=["bob"]))
    assert resp.status_code == 201
    assert Follow.objects.filter(follower=alice, following=bob).exists()

    resp = c.delete(reverse("v1:social:follow", args=["bob"]))
    assert resp.status_code == 204
    assert not Follow.objects.filter(follower=alice, following=bob).exists()


def test_cannot_follow_self(client_for, alice):
    resp = client_for(alice).post(reverse("v1:social:follow", args=["alice"]))
    assert resp.status_code == 400


def test_follow_respects_who_can_follow_nobody(client_for, alice, bob):
    bob.privacy.who_can_follow = Visibility.NOBODY
    bob.privacy.save()
    resp = client_for(alice).post(reverse("v1:social:follow", args=["bob"]))
    assert resp.status_code == 403


# -------------------------------------------------------------- friend requests
def test_friend_request_accept_creates_friendship(client_for, alice, bob):
    send = client_for(alice).post(reverse("v1:social:fr-send", args=["bob"]))
    assert send.status_code == 201
    fr = FriendRequest.objects.get(from_user=alice, to_user=bob)
    assert fr.status == FriendRequestStatus.PENDING

    accept = client_for(bob).post(reverse("v1:social:fr-accept", args=[fr.id]))
    assert accept.status_code == 200
    assert SocialService.are_friends(alice, bob)


def test_mutual_request_auto_accepts(client_for, alice, bob):
    client_for(alice).post(reverse("v1:social:fr-send", args=["bob"]))
    # Bob sending back accepts the existing request immediately.
    resp = client_for(bob).post(reverse("v1:social:fr-send", args=["alice"]))
    assert resp.status_code == 201
    assert SocialService.are_friends(alice, bob)


def test_only_recipient_can_accept(client_for, alice, bob):
    client_for(alice).post(reverse("v1:social:fr-send", args=["bob"]))
    fr = FriendRequest.objects.get(from_user=alice, to_user=bob)
    # Alice (the sender) cannot accept her own request.
    resp = client_for(alice).post(reverse("v1:social:fr-accept", args=[fr.id]))
    assert resp.status_code == 403


def test_cancel_and_reject_friend_request(client_for, alice, bob):
    client_for(alice).post(reverse("v1:social:fr-send", args=["bob"]))
    fr = FriendRequest.objects.get(from_user=alice, to_user=bob)
    resp = client_for(bob).post(reverse("v1:social:fr-reject", args=[fr.id]))
    assert resp.status_code == 200
    fr.refresh_from_db()
    assert fr.status == FriendRequestStatus.REJECTED


# ---------------------------------------------------------------------- block
def test_block_severs_follow_friendship_and_pending(client_for, alice, bob):
    SocialService.follow(actor=alice, target=bob)
    SocialService.follow(actor=bob, target=alice)
    # Make them friends.
    fr = SocialService.send_friend_request(actor=alice, target=bob)
    SocialService.accept_friend_request(actor=bob, request=fr)
    assert SocialService.are_friends(alice, bob)

    resp = client_for(alice).post(reverse("v1:social:block", args=["bob"]))
    assert resp.status_code == 201
    assert Block.objects.filter(blocker=alice, blocked=bob).exists()
    # All ties severed.
    assert not Follow.objects.filter(follower__in=[alice, bob], following__in=[alice, bob]).exists()
    assert not SocialService.are_friends(alice, bob)


def test_cannot_follow_when_blocked(client_for, alice, bob):
    SocialService.block(actor=bob, target=alice)
    resp = client_for(alice).post(reverse("v1:social:follow", args=["bob"]))
    assert resp.status_code == 403


def test_unblock(client_for, alice, bob):
    SocialService.block(actor=alice, target=bob)
    resp = client_for(alice).delete(reverse("v1:social:block", args=["bob"]))
    assert resp.status_code == 204
    assert not Block.objects.filter(blocker=alice, blocked=bob).exists()


# ----------------------------------------------------------------------- mute
def test_mute_and_unmute(client_for, alice, bob):
    resp = client_for(alice).post(reverse("v1:social:mute", args=["bob"]), {}, format="json")
    assert resp.status_code == 201
    assert Mute.objects.filter(muter=alice, muted=bob).exists()

    resp = client_for(alice).delete(reverse("v1:social:mute", args=["bob"]))
    assert resp.status_code == 204


# ----------------------------------------------------------------------- lists
def test_followers_following_and_friends_lists(client_for, alice, bob):
    SocialService.follow(actor=alice, target=bob)
    fr = SocialService.send_friend_request(actor=alice, target=bob)
    SocialService.accept_friend_request(actor=bob, request=fr)

    following = client_for(alice).get(reverse("v1:social:following"))
    assert [u["username"] for u in following.data["results"]] == ["bob"]

    followers = client_for(bob).get(reverse("v1:social:followers"))
    assert [u["username"] for u in followers.data["results"]] == ["alice"]

    friends = client_for(alice).get(reverse("v1:social:friends"))
    assert [u["username"] for u in friends.data["results"]] == ["bob"]


def test_incoming_outgoing_request_lists(client_for, alice, bob):
    SocialService.send_friend_request(actor=alice, target=bob)
    outgoing = client_for(alice).get(reverse("v1:social:fr-outgoing"))
    assert outgoing.data["count"] == 1
    incoming = client_for(bob).get(reverse("v1:social:fr-incoming"))
    assert incoming.data["count"] == 1
