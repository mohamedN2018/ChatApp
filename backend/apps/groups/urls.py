"""Group routes (mounted under /api/v1/groups/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "groups"

urlpatterns = [
    path("", views.GroupListCreateView.as_view(), name="list"),
    # Literal paths must precede the <slug> routes so they aren't captured as a slug.
    path("discover/", views.GroupDiscoverView.as_view(), name="discover"),
    path("join/", views.JoinByInviteView.as_view(), name="join-invite"),
    # Group-scoped
    path("<slug:slug>/", views.GroupDetailView.as_view(), name="detail"),
    path("<slug:slug>/avatar/", views.GroupAvatarView.as_view(), name="avatar"),
    path("<slug:slug>/banner/", views.GroupBannerView.as_view(), name="banner"),
    path("<slug:slug>/leave/", views.LeaveGroupView.as_view(), name="leave"),
    path("<slug:slug>/join/", views.JoinPublicView.as_view(), name="join-public"),
    path("<slug:slug>/transfer/", views.TransferOwnershipView.as_view(), name="transfer"),
    path("<slug:slug>/members/", views.MemberListView.as_view(), name="members"),
    path("<slug:slug>/members/<uuid:user_id>/", views.MemberView.as_view(), name="member"),
    path("<slug:slug>/channels/", views.ChannelListCreateView.as_view(), name="channels"),
    path(
        "<slug:slug>/channels/<uuid:channel_id>/",
        views.ChannelDetailView.as_view(),
        name="channel",
    ),
    path("<slug:slug>/invites/", views.InviteListCreateView.as_view(), name="invites"),
]
