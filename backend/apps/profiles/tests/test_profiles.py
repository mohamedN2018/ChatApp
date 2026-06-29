"""Tests for profile retrieval/update, privacy gating, image upload, settings."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.profiles.models import PresenceStatus, Profile, Visibility
from apps.social.services import SocialService

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


def png_bytes(size=(64, 64)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (90, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


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


def test_profile_is_auto_created_with_settings(alice):
    assert Profile.objects.filter(user=alice).exists()
    assert hasattr(alice, "privacy")
    assert hasattr(alice, "notification_settings")


def test_get_and_update_my_profile(client_for, alice):
    c = client_for(alice)
    assert c.get(reverse("v1:profiles:me")).status_code == 200

    resp = c.patch(
        reverse("v1:profiles:me"),
        {"bio": "Hello world", "status": PresenceStatus.BUSY, "country": "EG"},
        format="json",
    )
    assert resp.status_code == 200
    alice.profile.refresh_from_db()
    assert alice.profile.bio == "Hello world"
    assert alice.profile.status == PresenceStatus.BUSY


def test_public_profile_visible_to_others(client_for, alice, bob):
    resp = client_for(bob).get(reverse("v1:profiles:public", args=["alice"]))
    assert resp.status_code == 200
    assert resp.data["user"]["username"] == "alice"
    assert resp.data["relationship"]["is_following"] is False


def test_private_profile_blocks_non_friends(client_for, alice, bob):
    alice.privacy.profile_visibility = Visibility.NOBODY
    alice.privacy.save()
    # Others get 403; the owner can still see it.
    assert client_for(bob).get(reverse("v1:profiles:public", args=["alice"])).status_code == 403
    assert client_for(alice).get(reverse("v1:profiles:public", args=["alice"])).status_code == 200


def test_friends_only_profile(client_for, alice, bob):
    alice.privacy.profile_visibility = Visibility.FRIENDS
    alice.privacy.save()
    assert client_for(bob).get(reverse("v1:profiles:public", args=["alice"])).status_code == 403

    fr = SocialService.send_friend_request(actor=bob, target=alice)
    SocialService.accept_friend_request(actor=alice, request=fr)
    assert client_for(bob).get(reverse("v1:profiles:public", args=["alice"])).status_code == 200


def test_blocked_user_cannot_see_profile(client_for, alice, bob):
    SocialService.block(actor=alice, target=bob)
    # Blocked viewer gets 404 (existence hidden).
    assert client_for(bob).get(reverse("v1:profiles:public", args=["alice"])).status_code == 404


def test_avatar_upload_and_delete(client_for, alice, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    c = client_for(alice)
    upload = SimpleUploadedFile("avatar.png", png_bytes(), content_type="image/png")
    resp = c.post(reverse("v1:profiles:me-avatar"), {"image": upload}, format="multipart")
    assert resp.status_code == 200
    alice.profile.refresh_from_db()
    assert alice.profile.avatar  # stored (re-encoded to webp)
    assert alice.profile.avatar.name.endswith(".webp")

    resp = c.delete(reverse("v1:profiles:me-avatar"))
    assert resp.status_code == 204


def test_avatar_upload_rejects_non_image(client_for, alice, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    bad = SimpleUploadedFile("notimage.png", b"this is not an image", content_type="image/png")
    resp = client_for(alice).post(
        reverse("v1:profiles:me-avatar"), {"image": bad}, format="multipart"
    )
    assert resp.status_code == 400


def test_privacy_and_notification_settings_update(client_for, alice):
    c = client_for(alice)
    resp = c.patch(
        reverse("v1:profiles:me-privacy"),
        {"profile_visibility": Visibility.FRIENDS, "searchable": False},
        format="json",
    )
    assert resp.status_code == 200
    alice.privacy.refresh_from_db()
    assert alice.privacy.profile_visibility == Visibility.FRIENDS
    assert alice.privacy.searchable is False

    resp = c.patch(
        reverse("v1:profiles:me-notifications"),
        {"email_messages": False},
        format="json",
    )
    assert resp.status_code == 200
    alice.notification_settings.refresh_from_db()
    assert alice.notification_settings.email_messages is False
