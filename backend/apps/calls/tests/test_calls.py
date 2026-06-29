"""
Call tests: REST lifecycle (initiate/accept/reject/end, history, ICE) and a
WebSocket signaling-relay round-trip (offer relayed between peers).
"""

from __future__ import annotations

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.calls.consumers import CallConsumer
from apps.calls.models import Call, CallStatus
from apps.calls.services import CallService
from apps.chat.services import ChatService

User = get_user_model()


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


# ---------------------------------------------------------------- REST lifecycle
@pytest.mark.django_db
class TestCallLifecycle:
    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.conv = ChatService.get_or_create_direct(user_a=self.alice, user_b=self.bob)

    def _initiate(self, video=False):
        resp = client_for(self.alice).post(
            reverse("v1:calls:initiate"),
            {"conversation_id": str(self.conv.id), "type": "video" if video else "audio"},
            format="json",
        )
        assert resp.status_code == 201
        return resp.data

    def test_initiate_creates_ringing_call_with_initiator_joined(self):
        data = self._initiate(video=True)
        assert data["status"] == CallStatus.RINGING
        assert data["type"] == "video"
        assert any(
            p["user"]["username"] == "alice" and p["state"] == "joined"
            for p in data["participants"]
        )

    def test_accept_moves_call_to_ongoing(self):
        call = self._initiate()
        resp = client_for(self.bob).post(reverse("v1:calls:accept", args=[call["id"]]))
        assert resp.status_code == 200
        assert resp.data["status"] == CallStatus.ONGOING
        assert resp.data["started_at"] is not None

    def test_reject_ends_one_to_one_call(self):
        call = self._initiate()
        resp = client_for(self.bob).post(reverse("v1:calls:reject", args=[call["id"]]))
        assert resp.status_code == 204
        assert Call.objects.get(id=call["id"]).status == CallStatus.REJECTED

    def test_end_terminates_call(self):
        call = self._initiate()
        client_for(self.bob).post(reverse("v1:calls:accept", args=[call["id"]]))
        resp = client_for(self.alice).post(
            reverse("v1:calls:end", args=[call["id"]]), {"end": "true"}, format="json"
        )
        assert resp.status_code == 204
        ended = Call.objects.get(id=call["id"])
        assert ended.status == CallStatus.ENDED
        assert ended.ended_at is not None

    def test_outsider_cannot_initiate(self):
        outsider = make_user("outsider")
        resp = client_for(outsider).post(
            reverse("v1:calls:initiate"),
            {"conversation_id": str(self.conv.id), "type": "audio"},
            format="json",
        )
        assert resp.status_code == 403

    def test_ice_servers_endpoint(self):
        resp = client_for(self.alice).get(reverse("v1:calls:ice-servers"))
        assert resp.status_code == 200
        assert "iceServers" in resp.data
        assert resp.data["iceServers"][0]["urls"]

    def test_call_history(self):
        self._initiate()
        resp = client_for(self.bob).get(reverse("v1:calls:history"))
        assert resp.data["count"] == 1


# ----------------------------------------------------------- WebSocket signaling
@database_sync_to_async
def _acreate(username):
    return make_user(username)


@database_sync_to_async
def _setup_call(alice, bob):
    conv = ChatService.get_or_create_direct(user_a=alice, user_b=bob)
    return CallService.initiate(initiator=alice, conversation=conv)


async def _connect(user):
    communicator = WebsocketCommunicator(CallConsumer.as_asgi(), "/ws/calls/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    return communicator


@pytest.mark.django_db(transaction=True)
async def test_call_signaling_relay_between_peers():
    alice = await _acreate("alice")
    bob = await _acreate("bob")
    call = await _setup_call(alice, bob)

    comm_a = await _connect(alice)
    comm_b = await _connect(bob)

    # Bob joins the call over the socket.
    await comm_b.send_json_to({"action": "join", "call_id": str(call.id)})

    # Alice (initiator) is notified bob accepted; bob sees his own join in the room.
    accepted = await comm_a.receive_json_from()
    assert accepted["event"] == "call.accepted"
    joined = await comm_b.receive_json_from()
    assert joined["event"] == "peer.joined"

    # Alice sends an SDP offer targeted at bob; bob receives the relayed signal.
    await comm_a.send_json_to(
        {
            "action": "signal",
            "call_id": str(call.id),
            "to_user_id": str(bob.id),
            "data": {"type": "offer", "sdp": "v=0..."},
        }
    )
    signal = await comm_b.receive_json_from()
    assert signal["event"] == "call.signal"
    assert signal["from_user_id"] == str(alice.id)
    assert signal["data"]["type"] == "offer"

    await comm_a.disconnect()
    await comm_b.disconnect()
