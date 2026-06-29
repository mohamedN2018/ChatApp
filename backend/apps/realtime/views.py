"""Bulk presence query (REST). Useful for an initial render before the client
opens the presence WebSocket, or as a fallback."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.models import PresenceStatus
from apps.social.services import SocialService

from .presence import PresenceTracker, resolve_visible_status

User = get_user_model()
MAX_IDS = 200


@extend_schema(tags=["presence"])
class PresenceQueryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Resolve presence for a set of users",
        parameters=[
            OpenApiParameter(
                name="user_ids",
                description="Comma-separated user UUIDs (max 200).",
                required=True,
                type=str,
            )
        ],
    )
    def get(self, request):
        raw = request.query_params.get("user_ids", "")
        uids = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                uids.append(str(uuid.UUID(token)))
            except ValueError:
                continue
        uids = uids[:MAX_IDS]

        online = PresenceTracker.online_among(uids) if uids else set()
        users = User.objects.filter(pk__in=uids).select_related("profile", "privacy")

        result = []
        for user in users:
            are_friends = SocialService.are_friends(request.user, user)
            visible = resolve_visible_status(
                user, is_online=str(user.id) in online, are_friends=are_friends
            )
            last_seen = None
            if visible == PresenceStatus.OFFLINE and user.last_seen_at:
                last_seen = user.last_seen_at.isoformat()
            result.append({"user_id": str(user.id), "status": str(visible), "last_seen": last_seen})
        return Response({"users": result})
