"""Chat routes (mounted under /api/v1/chat/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("conversations/", views.ConversationListView.as_view(), name="conversation-list"),
    path("conversations/start/", views.StartConversationView.as_view(), name="conversation-start"),
    path(
        "conversations/<uuid:conversation_id>/",
        views.ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/state/",
        views.ConversationStateView.as_view(),
        name="conversation-state",
    ),
    path(
        "conversations/<uuid:conversation_id>/read/",
        views.MarkReadView.as_view(),
        name="conversation-read",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/",
        views.MessageListCreateView.as_view(),
        name="message-list",
    ),
    path("messages/<uuid:message_id>/", views.MessageDetailView.as_view(), name="message-detail"),
    path(
        "messages/<uuid:message_id>/react/", views.MessageReactView.as_view(), name="message-react"
    ),
]
