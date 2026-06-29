"""
Media tests: direct upload + image processing (Pillow), chunked upload assembly,
access control, and attaching media to a chat message.

Celery runs eagerly in tests, so processing completes synchronously. Storage is
in-memory (test settings). Image processing uses Pillow (no FFmpeg needed).
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.chat.services import ChatService
from apps.media.models import MediaFile, MediaKind, MediaStatus, UploadSession

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


def png_bytes(size=(80, 60)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def alice():
    return make_user("alice")


@pytest.fixture
def bob():
    return make_user("bob")


# --------------------------------------------------------------- direct upload
def test_direct_image_upload_is_processed(alice):
    upload = SimpleUploadedFile("pic.png", png_bytes((80, 60)), content_type="image/png")
    resp = client_for(alice).post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
    assert resp.status_code == 201
    assert resp.data["kind"] == MediaKind.IMAGE
    # Processing is async; the upload response is "pending". The eager task has
    # since updated the DB row, so assert the processed result there.
    media = MediaFile.objects.get(pk=resp.data["id"])
    assert media.owner == alice
    assert media.status == MediaStatus.READY
    assert media.width == 80 and media.height == 60
    assert media.thumbnail  # a WebP thumbnail was generated
    assert media.size > 0


def test_signed_download_url_streams_and_rejects_bad_token(alice):
    upload = SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png")
    data = (
        client_for(alice)
        .post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
        .data
    )
    url = data["url"]
    assert url.startswith("/api/v1/media/") and "token=" in url

    # The signed URL works with no auth header (usable in <img>).
    ok = APIClient().get(url)
    assert ok.status_code == 200
    # A tampered token is rejected.
    bad = url.split("?")[0] + "?token=tampered"
    assert APIClient().get(bad).status_code == 403


def test_direct_non_image_upload_is_kind_file(alice):
    upload = SimpleUploadedFile("notes.txt", b"hello world", content_type="text/plain")
    resp = client_for(alice).post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
    assert resp.status_code == 201
    assert resp.data["kind"] == MediaKind.FILE
    assert MediaFile.objects.get(pk=resp.data["id"]).status == MediaStatus.READY


# --------------------------------------------------------------- chunked upload
def test_chunked_upload_assembles_file(alice):
    c = client_for(alice)
    payload = b"0123456789" * 50  # 500 bytes
    mid = len(payload) // 2
    chunks = [payload[:mid], payload[mid:]]

    start = c.post(
        reverse("v1:media:upload-start"),
        {
            "filename": "blob.bin",
            "content_type": "application/octet-stream",
            "total_size": len(payload),
            "total_chunks": 2,
        },
        format="json",
    )
    assert start.status_code == 201
    upload_id = start.data["id"]

    for index, chunk in enumerate(chunks):
        part = SimpleUploadedFile(f"c{index}", chunk)
        r = c.put(
            reverse("v1:media:upload-chunk", args=[upload_id, index]),
            {"chunk": part},
            format="multipart",
        )
        assert r.status_code == 200

    status = c.get(reverse("v1:media:upload-session", args=[upload_id]))
    assert status.data["is_complete"] is True

    complete = c.post(reverse("v1:media:upload-complete", args=[upload_id]))
    assert complete.status_code == 201
    media = MediaFile.objects.get(pk=complete.data["id"])
    with media.file.open("rb") as fh:
        assert fh.read() == payload
    # Session marked completed and chunk objects cleaned up.
    session = UploadSession.objects.get(pk=upload_id)
    assert session.status == "completed"


def test_complete_before_all_chunks_fails(alice):
    c = client_for(alice)
    start = c.post(
        reverse("v1:media:upload-start"),
        {"filename": "x.bin", "total_size": 10, "total_chunks": 2},
        format="json",
    )
    upload_id = start.data["id"]
    c.put(
        reverse("v1:media:upload-chunk", args=[upload_id, 0]),
        {"chunk": SimpleUploadedFile("c0", b"12345")},
        format="multipart",
    )
    assert c.post(reverse("v1:media:upload-complete", args=[upload_id])).status_code == 400


# ----------------------------------------------------------------- access control
def test_media_access_is_restricted_then_shared_via_chat(alice, bob):
    # Alice uploads.
    upload = SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png")
    media_id = (
        client_for(alice)
        .post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
        .data["id"]
    )

    # Bob cannot access it yet.
    assert client_for(bob).get(reverse("v1:media:detail", args=[media_id])).status_code == 403

    # Alice shares it in a conversation with Bob.
    conv = ChatService.get_or_create_direct(user_a=alice, user_b=bob)
    ChatService.send_message(sender=alice, conversation=conv, text="", attachment_ids=[media_id])

    # Now Bob (a participant) can access it.
    assert client_for(bob).get(reverse("v1:media:detail", args=[media_id])).status_code == 200


# ------------------------------------------------------- attachment in a message
def test_send_message_with_attachment_sets_type_and_attachments(alice, bob):
    upload = SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png")
    media_id = (
        client_for(alice)
        .post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
        .data["id"]
    )

    conv = ChatService.get_or_create_direct(user_a=alice, user_b=bob)
    resp = client_for(alice).post(
        reverse("v1:chat:message-list", args=[conv.id]),
        {"attachment_ids": [media_id]},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["type"] == "image"
    assert len(resp.data["attachments"]) == 1
    assert resp.data["attachments"][0]["id"] == media_id


def test_cannot_attach_someone_elses_media(alice, bob):
    upload = SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png")
    alice_media = (
        client_for(alice)
        .post(reverse("v1:media:upload"), {"file": upload}, format="multipart")
        .data["id"]
    )

    conv = ChatService.get_or_create_direct(user_a=alice, user_b=bob)
    # Bob tries to attach Alice's media.
    resp = client_for(bob).post(
        reverse("v1:chat:message-list", args=[conv.id]),
        {"attachment_ids": [alice_media]},
        format="json",
    )
    assert resp.status_code == 400
