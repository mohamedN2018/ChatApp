"""Realtime/presence REST routes (mounted under /api/v1/presence/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "realtime"

urlpatterns = [
    path("", views.PresenceQueryView.as_view(), name="presence-query"),
]
