"""
Presence tests: the REST bulk query and the WebSocket consumer.

Redis is faked (project conftest autouse fixture) and the channel layer is the
in-memory layer (test settings), so these run with no external services.
"""

from __future__ import annotations

import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.profiles.models import PresenceStatus, Visibility
from apps.realtime.consumers import PresenceConsumer
from apps.realtime.presence import PresenceTracker

User = get_user_model()


def make_user(username):
    return User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )


# ----------------------------------------------------------------- REST query
@pytest.mark.django_db
def test_presence_query_reflects_connection_state():
    alice, bob = make_user("alice"), make_user("bob")
    client = APIClient()
    client.force_authenticate(alice)
    url = reverse("v1:realtime:presence-query") + f"?user_ids={bob.id}"

    # Offline initially.
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data["users"][0]["status"] == "offline"

    # Mark online (as the consumer would on connect).
    PresenceTracker.add_connection(str(bob.id), "chan-1")
    resp = client.get(url)
    assert resp.data["users"][0]["status"] == "online"


@pytest.mark.django_db
def test_presence_query_honours_invisible_mode():
    alice, bob = make_user("alice"), make_user("bob")
    bob.profile.status = PresenceStatus.INVISIBLE
    bob.profile.save()
    PresenceTracker.add_connection(str(bob.id), "chan-1")

    client = APIClient()
    client.force_authenticate(alice)
    resp = client.get(reverse("v1:realtime:presence-query") + f"?user_ids={bob.id}")
    # Connected but invisible -> appears offline.
    assert resp.data["users"][0]["status"] == "offline"


@pytest.mark.django_db
def test_presence_query_honours_friends_only_visibility():
    alice, bob = make_user("alice"), make_user("bob")
    bob.privacy.online_status_visibility = Visibility.FRIENDS
    bob.privacy.save()
    PresenceTracker.add_connection(str(bob.id), "chan-1")

    client = APIClient()
    client.force_authenticate(alice)
    resp = client.get(reverse("v1:realtime:presence-query") + f"?user_ids={bob.id}")
    # Not friends -> online status hidden.
    assert resp.data["users"][0]["status"] == "offline"


# ------------------------------------------------------------ WebSocket consumer
@pytest.mark.django_db(transaction=True)
async def test_presence_consumer_connect_set_status():
    alice = await _acreate("alice")
    communicator = WebsocketCommunicator(PresenceConsumer.as_asgi(), "/ws/presence/")
    communicator.scope["user"] = alice
    connected, _ = await communicator.connect()
    assert connected

    hello = await communicator.receive_json_from()
    assert hello["type"] == "presence.self"
    assert hello["status"] == "online"

    await communicator.send_json_to({"action": "set_status", "status": "away"})
    updated = await communicator.receive_json_from()
    assert updated["type"] == "presence.self"
    assert updated["status"] == "away"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_presence_fanout_on_subscribe_and_disconnect():
    alice = await _acreate("alice")
    bob = await _acreate("bob")

    comm_a = WebsocketCommunicator(PresenceConsumer.as_asgi(), "/ws/presence/")
    comm_a.scope["user"] = alice
    assert (await comm_a.connect())[0]
    await comm_a.receive_json_from()  # presence.self

    comm_b = WebsocketCommunicator(PresenceConsumer.as_asgi(), "/ws/presence/")
    comm_b.scope["user"] = bob
    assert (await comm_b.connect())[0]
    await comm_b.receive_json_from()  # presence.self

    # Bob watches Alice -> snapshot shows her online.
    await comm_b.send_json_to({"action": "subscribe", "user_ids": [str(alice.id)]})
    snapshot = await comm_b.receive_json_from()
    assert snapshot["type"] == "presence.snapshot"
    assert snapshot["users"][0]["user_id"] == str(alice.id)
    assert snapshot["users"][0]["status"] == "online"

    # Alice disconnects -> Bob receives a live offline update.
    await comm_a.disconnect()
    update = await comm_b.receive_json_from()
    assert update["type"] == "presence.update"
    assert update["user_id"] == str(alice.id)
    assert update["status"] == "offline"

    await comm_b.disconnect()


async def _acreate(username):
    from channels.db import database_sync_to_async

    return await database_sync_to_async(make_user)(username)
