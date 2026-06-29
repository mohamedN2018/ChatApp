"""Tests for liveness/readiness probes and the base model behaviour."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_liveness_is_public_and_ok(client):
    resp = client.get(reverse("health-live"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readiness_reports_dependency_checks(client):
    resp = client.get(reverse("health-ready"))
    # On the test stack (sqlite + locmem cache + in-memory channel layer) every
    # dependency is healthy, so readiness must be 200/ready.
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert set(body["checks"]) == {"database", "cache", "channel_layer"}
    assert all(check["ok"] for check in body["checks"].values())
