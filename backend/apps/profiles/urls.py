"""Profile routes (mounted under /api/v1/profiles/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("me/", views.MeProfileView.as_view(), name="me"),
    path("me/avatar/", views.AvatarView.as_view(), name="me-avatar"),
    path("me/cover/", views.CoverView.as_view(), name="me-cover"),
    path("me/privacy/", views.PrivacySettingsView.as_view(), name="me-privacy"),
    path("me/notifications/", views.NotificationSettingsView.as_view(), name="me-notifications"),
    # Keep this last: a username path segment must not shadow the /me/ routes.
    path("<str:username>/", views.PublicProfileView.as_view(), name="public"),
]
