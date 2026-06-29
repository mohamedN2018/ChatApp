"""
Project-wide pytest fixtures.

Presence relies on Redis SET operations that the local-memory cache can't model,
so every test runs against an in-memory fakeredis instead of a real server. The
patch is autouse so no test accidentally reaches for a live Redis.
"""

from __future__ import annotations

import fakeredis
import pytest


@pytest.fixture(autouse=True)
def _fake_presence_redis(monkeypatch):
    from apps.realtime import presence

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(presence, "_client", client)
    yield client


@pytest.fixture(autouse=True)
def _clear_cache():
    """The locmem cache persists across tests; clear it so cached singletons
    (e.g. SystemConfig / maintenance mode) and throttle counters don't leak."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
