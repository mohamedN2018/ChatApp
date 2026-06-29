"""
Administration tests: reporting, admin-only access, dashboard, feature flags,
announcements, system config, audit logging, maintenance mode, and i18n.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.administration.models import AdminAuditLog, FeatureFlag, Report

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(username, staff=False):
    user = User.objects.create_user(
        email=f"{username}@example.com", username=username, password="Sup3rSecret!pw"
    )
    if staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    return user


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def user():
    return make_user("normal")


@pytest.fixture
def admin():
    return make_user("boss", staff=True)


# ---------------------------------------------------------------- user-facing
def test_user_can_create_report(user):
    resp = client_for(user).post(
        reverse("v1:administration:report-create"),
        {"target_type": "user", "target_id": str(uuid.uuid4()), "reason": "spam"},
        format="json",
    )
    assert resp.status_code == 201
    assert Report.objects.filter(reporter=user, reason="spam").exists()


def test_languages_endpoint(user):
    resp = client_for(user).get(reverse("v1:administration:languages"))
    assert resp.status_code == 200
    codes = {lang["code"] for lang in resp.data["languages"]}
    assert {"en", "ar"} <= codes


def test_x_language_header_sets_content_language(user):
    resp = client_for(user).get(reverse("v1:administration:languages"), HTTP_X_LANGUAGE="ar")
    assert resp.headers.get("Content-Language") == "ar"


# ---------------------------------------------------------------- admin access
def test_non_admin_blocked_from_admin_endpoints(user):
    assert client_for(user).get(reverse("v1:administration:dashboard")).status_code == 403


def test_dashboard_returns_stats(admin):
    resp = client_for(admin).get(reverse("v1:administration:dashboard"))
    assert resp.status_code == 200
    assert "users" in resp.data and "messages" in resp.data and "charts" in resp.data


def test_report_moderation_flow(admin, user):
    report = Report.objects.create(
        reporter=user, target_type="user", target_id=uuid.uuid4(), reason="abuse"
    )
    resp = client_for(admin).patch(
        reverse("v1:administration:admin-report", args=[report.id]),
        {"status": "resolved", "resolution_notes": "warned"},
        format="json",
    )
    assert resp.status_code == 200
    report.refresh_from_db()
    assert report.status == "resolved"
    assert report.handled_by == admin
    assert AdminAuditLog.objects.filter(action="report.updated").exists()


def test_feature_flag_create_toggle_and_public_list(admin, user):
    create = client_for(admin).post(
        reverse("v1:administration:admin-flags"),
        {"key": "new-ui", "is_enabled": True, "description": "New UI"},
        format="json",
    )
    assert create.status_code == 201
    # Public enabled-flags endpoint reflects it.
    resp = client_for(user).get(reverse("v1:administration:flags"))
    assert "new-ui" in resp.data["flags"]
    # Toggle off.
    client_for(admin).patch(
        reverse("v1:administration:admin-flag", args=["new-ui"]),
        {"is_enabled": False},
        format="json",
    )
    assert FeatureFlag.is_active("new-ui") is False


def test_announcement_create_and_active_list(admin, user):
    client_for(admin).post(
        reverse("v1:administration:admin-announcements"),
        {"title": "Welcome", "body": "Hello", "level": "info", "is_active": True},
        format="json",
    )
    resp = client_for(user).get(reverse("v1:administration:announcements"))
    assert any(a["title"] == "Welcome" for a in resp.data)


def test_admin_user_management(admin, user):
    resp = client_for(admin).patch(
        reverse("v1:administration:admin-user", args=[user.id]),
        {"is_verified": True},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.is_verified is True


# ---------------------------------------------------------------- maintenance
def test_maintenance_mode_blocks_normal_traffic_but_not_health_or_admin(admin, user):
    # Admin turns maintenance on (admin API is allowlisted).
    resp = client_for(admin).patch(
        reverse("v1:administration:admin-system"),
        {"maintenance_mode": True},
        format="json",
    )
    assert resp.status_code == 200

    public = APIClient()
    # Health always works.
    assert public.get(reverse("health-live")).status_code == 200
    # A normal API endpoint is blocked with 503.
    assert client_for(user).get(reverse("v1:profiles:me")).status_code == 503
    # The admin API still works (so admins can turn it back off).
    off = client_for(admin).patch(
        reverse("v1:administration:admin-system"),
        {"maintenance_mode": False},
        format="json",
    )
    assert off.status_code == 200
    # Back to normal.
    assert client_for(user).get(reverse("v1:profiles:me")).status_code == 200
