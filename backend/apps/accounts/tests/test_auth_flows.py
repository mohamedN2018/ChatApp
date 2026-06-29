"""
End-to-end API tests for the authentication slice.

Covers the full lifecycle: register -> verify -> login -> access -> refresh ->
logout, plus password reset/change, session/device management, security logging,
and rate limiting. Celery runs eagerly in tests, so emails land in mail.outbox.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import SecurityEvent, SecurityEventType, UserSession

User = get_user_model()
pytestmark = pytest.mark.django_db

PASSWORD = "Sup3rSecret!pw"
TOKEN_RE = re.compile(r"token=([\w\-]+)")


# ------------------------------------------------------------------- fixtures
@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _token_from_outbox(subject_contains: str) -> str:
    msg = next(m for m in mail.outbox if subject_contains.lower() in m.subject.lower())
    match = TOKEN_RE.search(msg.body)
    assert match, f"no token found in email: {msg.body!r}"
    return match.group(1)


def _register(client, email="alice@example.com", username="alice"):
    return client.post(
        reverse("v1:accounts:register"),
        {
            "email": email,
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
        format="json",
    )


def _login(client, email="alice@example.com", password=PASSWORD):
    return client.post(
        reverse("v1:accounts:login"),
        {"email": email, "password": password},
        format="json",
    )


@pytest.fixture
def verified_user(client):
    """Register + verify a user, returning the User instance."""
    _register(client)
    token = _token_from_outbox("confirm")
    client.post(reverse("v1:accounts:verify-email"), {"token": token}, format="json")
    return User.objects.get(username="alice")


@pytest.fixture
def auth(client, verified_user):
    """Logged-in client; returns (client, access, refresh)."""
    resp = _login(client)
    access = resp.data["access"]
    refresh = resp.data["refresh"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client, access, refresh


# --------------------------------------------------------------- registration
def test_register_creates_unverified_user_and_sends_email(client):
    resp = _register(client)
    assert resp.status_code == 201
    user = User.objects.get(email="alice@example.com")
    assert user.is_email_verified is False
    assert user.is_active is True
    assert len(mail.outbox) == 1
    assert "confirm" in mail.outbox[0].subject.lower()
    assert SecurityEvent.objects.filter(user=user, event_type=SecurityEventType.REGISTERED).exists()


def test_register_rejects_password_mismatch(client):
    resp = client.post(
        reverse("v1:accounts:register"),
        {
            "email": "b@example.com",
            "username": "bob",
            "password": PASSWORD,
            "password_confirm": "different",
        },
        format="json",
    )
    assert resp.status_code == 400


def test_register_rejects_weak_password(client):
    resp = client.post(
        reverse("v1:accounts:register"),
        {"email": "b@example.com", "username": "bob", "password": "123", "password_confirm": "123"},
        format="json",
    )
    assert resp.status_code == 400


def test_register_rejects_duplicate_email(client):
    _register(client)
    resp = _register(client, email="alice@example.com", username="alice2")
    assert resp.status_code == 400


# ---------------------------------------------------------------- verification
def test_verify_email_with_valid_token(client):
    _register(client)
    token = _token_from_outbox("confirm")
    resp = client.post(reverse("v1:accounts:verify-email"), {"token": token}, format="json")
    assert resp.status_code == 200
    assert User.objects.get(username="alice").is_email_verified is True


def test_verify_email_rejects_invalid_token(client):
    resp = client.post(reverse("v1:accounts:verify-email"), {"token": "nope"}, format="json")
    assert resp.status_code == 400


def test_verification_token_is_single_use(client):
    _register(client)
    token = _token_from_outbox("confirm")
    url = reverse("v1:accounts:verify-email")
    assert client.post(url, {"token": token}, format="json").status_code == 200
    # Reusing the consumed token fails.
    assert client.post(url, {"token": token}, format="json").status_code == 400


# ----------------------------------------------------------------------- login
def test_login_returns_tokens_and_creates_session(client, verified_user):
    resp = _login(client)
    assert resp.status_code == 200
    assert {"access", "refresh", "user"} <= set(resp.data)
    assert UserSession.objects.filter(user=verified_user, revoked_at__isnull=True).count() == 1
    assert SecurityEvent.objects.filter(
        user=verified_user, event_type=SecurityEventType.LOGIN
    ).exists()


def test_login_invalid_password_logs_failure(client, verified_user):
    resp = _login(client, password="wrong-password-xx")
    assert resp.status_code == 400
    assert SecurityEvent.objects.filter(event_type=SecurityEventType.LOGIN_FAILED).exists()


def test_me_requires_authentication(client):
    assert client.get(reverse("v1:accounts:me")).status_code == 401


def test_me_returns_current_user(auth):
    client, _access, _refresh = auth
    resp = client.get(reverse("v1:accounts:me"))
    assert resp.status_code == 200
    assert resp.data["username"] == "alice"
    assert resp.data["is_email_verified"] is True


# --------------------------------------------------------------------- refresh
def test_token_refresh_returns_new_access(client, auth):
    _client, _access, refresh = auth
    resp = client.post(reverse("v1:accounts:token-refresh"), {"refresh": refresh}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.data


# ---------------------------------------------------------------------- logout
def test_logout_revokes_session_immediately(client, auth):
    _client, access, refresh = auth
    # Logout the current session.
    resp = client.post(reverse("v1:accounts:logout"), {"refresh": refresh}, format="json")
    assert resp.status_code == 204
    # The access token is rejected at once (session revoked), even though it
    # hasn't expired.
    assert client.get(reverse("v1:accounts:me")).status_code == 401
    # The refresh token no longer works either.
    refresh_resp = client.post(
        reverse("v1:accounts:token-refresh"), {"refresh": refresh}, format="json"
    )
    assert refresh_resp.status_code == 401


# ------------------------------------------------------------ session management
def test_session_list_marks_current(auth):
    client, _access, _refresh = auth
    resp = client.get(reverse("v1:accounts:session-list"))
    assert resp.status_code == 200
    results = resp.data["results"]
    assert len(results) == 1
    assert results[0]["is_current"] is True
    assert results[0]["is_active"] is True


def test_revoke_other_session_signs_out_that_device(client, verified_user):
    # Two independent logins -> two sessions / token pairs.
    c1, c2 = APIClient(), APIClient()
    a1 = _login(c1).data["access"]
    a2 = _login(c2).data["access"]
    c1.credentials(HTTP_AUTHORIZATION=f"Bearer {a1}")
    c2.credentials(HTTP_AUTHORIZATION=f"Bearer {a2}")

    # From session 1, list sessions and revoke the *other* one.
    sessions = c1.get(reverse("v1:accounts:session-list")).data["results"]
    other = next(s for s in sessions if not s["is_current"])
    resp = c1.delete(reverse("v1:accounts:session-revoke", args=[other["id"]]))
    assert resp.status_code == 204

    # Session 2 is now signed out; session 1 still works.
    assert c2.get(reverse("v1:accounts:me")).status_code == 401
    assert c1.get(reverse("v1:accounts:me")).status_code == 200


def test_revoke_unknown_session_returns_404(auth):
    client, _a, _r = auth
    resp = client.delete(
        reverse("v1:accounts:session-revoke", args=["00000000-0000-0000-0000-000000000000"])
    )
    assert resp.status_code == 404


# ------------------------------------------------------------- password recovery
def test_password_reset_request_is_privacy_preserving(client, verified_user):
    # Existing email -> email sent.
    resp = client.post(
        reverse("v1:accounts:password-reset"), {"email": "alice@example.com"}, format="json"
    )
    assert resp.status_code == 200
    assert any("reset" in m.subject.lower() for m in mail.outbox)

    mail.outbox.clear()
    # Unknown email -> identical response, but no email.
    resp = client.post(
        reverse("v1:accounts:password-reset"), {"email": "ghost@example.com"}, format="json"
    )
    assert resp.status_code == 200
    assert len(mail.outbox) == 0


def test_password_reset_confirm_changes_password_and_revokes_sessions(client, verified_user):
    # Establish an active session, then reset.
    _login(client)
    assert UserSession.objects.filter(user=verified_user, revoked_at__isnull=True).count() == 1

    client.post(
        reverse("v1:accounts:password-reset"), {"email": "alice@example.com"}, format="json"
    )
    token = _token_from_outbox("reset")
    new_password = "Brand-New-Pw99"
    resp = client.post(
        reverse("v1:accounts:password-reset-confirm"),
        {"token": token, "new_password": new_password, "new_password_confirm": new_password},
        format="json",
    )
    assert resp.status_code == 200
    verified_user.refresh_from_db()
    assert verified_user.check_password(new_password)
    # All sessions revoked by the reset.
    assert UserSession.objects.filter(user=verified_user, revoked_at__isnull=True).count() == 0


def test_change_password_keeps_current_session_signs_out_others(client, verified_user):
    c1, c2 = APIClient(), APIClient()
    login1 = _login(c1).data
    _login(c2)
    c1.credentials(HTTP_AUTHORIZATION=f"Bearer {login1['access']}")

    new_password = "Another-Pw-123"
    resp = c1.post(
        reverse("v1:accounts:password-change"),
        {
            "current_password": PASSWORD,
            "new_password": new_password,
            "new_password_confirm": new_password,
        },
        format="json",
    )
    assert resp.status_code == 200
    # Current device still active; only one session remains.
    assert c1.get(reverse("v1:accounts:me")).status_code == 200
    assert UserSession.objects.filter(user=verified_user, revoked_at__isnull=True).count() == 1


def test_change_password_rejects_wrong_current(auth):
    client, _a, _r = auth
    resp = client.post(
        reverse("v1:accounts:password-change"),
        {
            "current_password": "definitely-wrong",
            "new_password": "Valid-New-Pw-1",
            "new_password_confirm": "Valid-New-Pw-1",
        },
        format="json",
    )
    assert resp.status_code == 400


# ----------------------------------------------------------------- security log
def test_security_log_lists_user_events(auth):
    client, _a, _r = auth
    resp = client.get(reverse("v1:accounts:security-log"))
    assert resp.status_code == 200
    types = {e["event_type"] for e in resp.data["results"]}
    assert SecurityEventType.REGISTERED in types
    assert SecurityEventType.LOGIN in types


# --------------------------------------------------------------------- throttle
def test_login_endpoint_is_rate_limited(client, verified_user, monkeypatch):
    # DRF binds THROTTLE_RATES at import time, so override_settings can't reach
    # it — patch the class attribute the scoped throttle actually reads. The
    # verified_user fixture has already run (with throttling disabled), so only
    # the "login" scope is exercised below.
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "2/min"})
    cache.clear()
    url = reverse("v1:accounts:login")
    payload = {"email": "alice@example.com", "password": "wrong"}
    assert client.post(url, payload, format="json").status_code == 400
    assert client.post(url, payload, format="json").status_code == 400
    # Third attempt within the window is throttled.
    assert client.post(url, payload, format="json").status_code == 429
