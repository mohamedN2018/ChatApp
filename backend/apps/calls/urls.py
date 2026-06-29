"""Call routes (mounted under /api/v1/calls/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "calls"

urlpatterns = [
    path("", views.CallHistoryView.as_view(), name="history"),
    path("initiate/", views.InitiateCallView.as_view(), name="initiate"),
    path("ice-servers/", views.IceServersView.as_view(), name="ice-servers"),
    path("<uuid:call_id>/", views.CallDetailView.as_view(), name="detail"),
    path("<uuid:call_id>/accept/", views.AcceptCallView.as_view(), name="accept"),
    path("<uuid:call_id>/reject/", views.RejectCallView.as_view(), name="reject"),
    path("<uuid:call_id>/end/", views.EndCallView.as_view(), name="end"),
]
