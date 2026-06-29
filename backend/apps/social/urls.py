"""Social routes (mounted under /api/v1/social/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    # My lists
    path("me/followers/", views.FollowersView.as_view(), name="followers"),
    path("me/following/", views.FollowingView.as_view(), name="following"),
    path("me/friends/", views.FriendsView.as_view(), name="friends"),
    path(
        "me/friend-requests/incoming/",
        views.IncomingFriendRequestsView.as_view(),
        name="fr-incoming",
    ),
    path(
        "me/friend-requests/outgoing/",
        views.OutgoingFriendRequestsView.as_view(),
        name="fr-outgoing",
    ),
    path("me/blocked/", views.BlockedListView.as_view(), name="blocked"),
    path("me/mutes/", views.MutedListView.as_view(), name="mutes"),
    # Friend-request actions by id
    path(
        "friend-requests/<uuid:pk>/accept/",
        views.FriendRequestActionView.as_view(action="accept"),
        name="fr-accept",
    ),
    path(
        "friend-requests/<uuid:pk>/reject/",
        views.FriendRequestActionView.as_view(action="reject"),
        name="fr-reject",
    ),
    path(
        "friend-requests/<uuid:pk>/cancel/",
        views.FriendRequestActionView.as_view(action="cancel"),
        name="fr-cancel",
    ),
    # Per-user actions
    path("users/<str:username>/follow/", views.FollowView.as_view(), name="follow"),
    path(
        "users/<str:username>/friend-request/",
        views.FriendRequestSendView.as_view(),
        name="fr-send",
    ),
    path("users/<str:username>/friend/", views.RemoveFriendView.as_view(), name="remove-friend"),
    path("users/<str:username>/block/", views.BlockView.as_view(), name="block"),
    path("users/<str:username>/mute/", views.MuteView.as_view(), name="mute"),
]
