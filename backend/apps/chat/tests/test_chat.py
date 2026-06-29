"""
Chat tests: conversations, messages (send/history/edit/delete), reactions, read
receipts (REST), and realtime delivery + typing over the WebSocket consumer.

WebSocket tests use the in-memory channel layer (test settings); messages sent
via the service broadcast through it to the other participant.
"""

from __future__ import annotations

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chat.consumers import ChatConsumer
from apps.chat.models import Conversation
from apps.chat.services import ChatService
from apps.social.services import SocialService

User = get_user_model()


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


def auth_client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


# ============================================================ REST: conversations
@pytest.mark.django_db
class TestConversationsAndMessages:
    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.ca = auth_client(self.alice)
        self.cb = auth_client(self.bob)

    def _start(self):
        resp = self.ca.post(
            reverse("v1:chat:conversation-start"), {"username": "bob"}, format="json"
        )
        assert resp.status_code == 201
        return resp.data["id"]

    def test_start_direct_is_idempotent(self):
        first = self._start()
        again = self.cb.post(
            reverse("v1:chat:conversation-start"), {"username": "alice"}, format="json"
        )
        assert again.data["id"] == first  # same conversation both directions
        assert Conversation.objects.filter(type="direct").count() == 1

    def test_cannot_start_with_self(self):
        resp = self.ca.post(
            reverse("v1:chat:conversation-start"), {"username": "alice"}, format="json"
        )
        assert resp.status_code == 400

    def test_cannot_start_when_blocked(self):
        SocialService.block(actor=self.bob, target=self.alice)
        resp = self.ca.post(
            reverse("v1:chat:conversation-start"), {"username": "bob"}, format="json"
        )
        assert resp.status_code == 403

    def test_send_and_list_messages(self):
        cid = self._start()
        url = reverse("v1:chat:message-list", args=[cid])
        send = self.ca.post(url, {"text": "hello bob", "client_id": "c1"}, format="json")
        assert send.status_code == 201
        assert send.data["text"] == "hello bob"
        assert send.data["metadata"]["client_id"] == "c1"

        history = self.cb.get(url)
        assert history.status_code == 200
        assert [m["text"] for m in history.data["results"]] == ["hello bob"]

    def test_empty_message_rejected(self):
        cid = self._start()
        resp = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "   "}, format="json"
        )
        assert resp.status_code == 400

    def test_unread_count_and_mark_read(self):
        cid = self._start()
        self.ca.post(reverse("v1:chat:message-list", args=[cid]), {"text": "yo"}, format="json")
        # Bob has one unread.
        convs = self.cb.get(reverse("v1:chat:conversation-list"))
        target = next(c for c in convs.data["results"] if c["id"] == cid)
        assert target["unread_count"] == 1
        # Mark read -> zero.
        assert self.cb.post(reverse("v1:chat:conversation-read", args=[cid])).status_code == 204
        convs = self.cb.get(reverse("v1:chat:conversation-list"))
        target = next(c for c in convs.data["results"] if c["id"] == cid)
        assert target["unread_count"] == 0

    def test_reply_to_message(self):
        cid = self._start()
        first = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "q?"}, format="json"
        ).data
        reply = self.cb.post(
            reverse("v1:chat:message-list", args=[cid]),
            {"text": "a!", "reply_to": first["id"]},
            format="json",
        )
        assert reply.status_code == 201
        assert reply.data["reply_to"]["id"] == first["id"]

    def test_edit_message_only_by_sender(self):
        cid = self._start()
        msg = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "typo"}, format="json"
        ).data
        url = reverse("v1:chat:message-detail", args=[msg["id"]])
        # Non-sender cannot edit.
        assert self.cb.patch(url, {"text": "hacked"}, format="json").status_code == 403
        # Sender can.
        edited = self.ca.patch(url, {"text": "fixed"}, format="json")
        assert edited.status_code == 200
        assert edited.data["text"] == "fixed" and edited.data["is_edited"] is True

    def test_delete_for_everyone_tombstones(self):
        cid = self._start()
        msg = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "oops"}, format="json"
        ).data
        url = reverse("v1:chat:message-detail", args=[msg["id"]]) + "?for_everyone=true"
        assert self.ca.delete(url).status_code == 204
        history = self.cb.get(reverse("v1:chat:message-list", args=[cid]))
        m = history.data["results"][0]
        assert m["deleted_for_everyone"] is True
        assert m["text"] == ""

    def test_delete_for_me_hides_only_for_actor(self):
        cid = self._start()
        msg = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "secret"}, format="json"
        ).data
        url = reverse("v1:chat:message-detail", args=[msg["id"]])
        assert self.cb.delete(url).status_code == 204  # bob hides it for himself
        assert self.cb.get(reverse("v1:chat:message-list", args=[cid])).data["results"] == []
        # Still visible to alice.
        assert len(self.ca.get(reverse("v1:chat:message-list", args=[cid])).data["results"]) == 1

    def test_reaction_toggle(self):
        cid = self._start()
        msg = self.ca.post(
            reverse("v1:chat:message-list", args=[cid]), {"text": "nice"}, format="json"
        ).data
        url = reverse("v1:chat:message-react", args=[msg["id"]])
        added = self.cb.post(url, {"emoji": "👍"}, format="json")
        assert added.data["reactions"][0]["emoji"] == "👍"
        assert added.data["reactions"][0]["count"] == 1
        # Toggling the same emoji removes it.
        removed = self.cb.post(url, {"emoji": "👍"}, format="json")
        assert removed.data["reactions"] == []


# ============================================================ WebSocket: realtime
@database_sync_to_async
def _acreate(username):
    return make_user(username)


@database_sync_to_async
def _astart(a, b):
    return ChatService.get_or_create_direct(user_a=a, user_b=b)


async def _connect(user):
    communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    return communicator


@pytest.mark.django_db(transaction=True)
async def test_chat_ws_delivers_message_to_both_participants():
    alice = await _acreate("alice")
    bob = await _acreate("bob")
    conversation = await _astart(alice, bob)

    comm_a = await _connect(alice)
    comm_b = await _connect(bob)

    await comm_a.send_json_to(
        {
            "action": "send",
            "conversation_id": str(conversation.id),
            "text": "hi bob",
            "client_id": "x1",
        }
    )

    received = await comm_b.receive_json_from()
    assert received["event"] == "message.new"
    assert received["message"]["text"] == "hi bob"
    assert received["message"]["metadata"]["client_id"] == "x1"

    # The sender is also a participant, so she gets the broadcast too.
    echoed = await comm_a.receive_json_from()
    assert echoed["event"] == "message.new"

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_chat_ws_typing_indicator():
    alice = await _acreate("alice")
    bob = await _acreate("bob")
    conversation = await _astart(alice, bob)

    comm_a = await _connect(alice)
    comm_b = await _connect(bob)

    await comm_a.send_json_to(
        {"action": "typing", "conversation_id": str(conversation.id), "state": "start"}
    )
    typing = await comm_b.receive_json_from()
    assert typing["event"] == "typing"
    assert typing["user_id"] == str(alice.id)
    assert typing["state"] == "start"

    await comm_a.disconnect()
    await comm_b.disconnect()
