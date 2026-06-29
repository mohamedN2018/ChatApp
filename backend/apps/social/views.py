"""
Social graph endpoints.

Action views resolve a target user from the ``username`` path segment and delegate
to ``SocialService``. List views are paginated and scoped to the requesting user.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.serializers import PublicUserSerializer

from .models import Block, FriendRequest, FriendRequestStatus, Friendship, Mute
from .serializers import (
    BlockSerializer,
    FriendRequestSerializer,
    MuteCreateSerializer,
    MuteSerializer,
)
from .services import SocialService

User = get_user_model()


class _TargetUserMixin:
    """Resolve the target user from the ``username`` kwarg."""

    permission_classes = [IsAuthenticated]

    def get_target(self):
        return get_object_or_404(User, username=self.kwargs["username"], is_active=True)


# ----------------------------------------------------------------------- follow
@extend_schema(tags=["social"])
class FollowView(_TargetUserMixin, APIView):
    @extend_schema(summary="Follow a user", responses={201: None})
    def post(self, request, username):
        SocialService.follow(actor=request.user, target=self.get_target())
        return Response({"detail": "Followed."}, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Unfollow a user", responses={204: None})
    def delete(self, request, username):
        SocialService.unfollow(actor=request.user, target=self.get_target())
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------- friend requests
@extend_schema(tags=["social"])
class FriendRequestSendView(_TargetUserMixin, APIView):
    @extend_schema(
        summary="Send (or auto-accept) a friend request", responses=FriendRequestSerializer
    )
    def post(self, request, username):
        fr = SocialService.send_friend_request(actor=request.user, target=self.get_target())
        return Response(FriendRequestSerializer(fr).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["social"])
class FriendRequestActionView(APIView):
    """Accept / reject / cancel a friend request by id."""

    permission_classes = [IsAuthenticated]
    action = ""  # set per-URL

    def get_request_obj(self):
        return get_object_or_404(FriendRequest, pk=self.kwargs["pk"])

    @extend_schema(summary="Act on a friend request", responses=FriendRequestSerializer)
    def post(self, request, pk):
        fr = self.get_request_obj()
        handler = {
            "accept": SocialService.accept_friend_request,
            "reject": SocialService.reject_friend_request,
            "cancel": SocialService.cancel_friend_request,
        }[self.action]
        fr = handler(actor=request.user, request=fr)
        return Response(FriendRequestSerializer(fr).data)


@extend_schema(tags=["social"])
class RemoveFriendView(_TargetUserMixin, APIView):
    @extend_schema(summary="Remove a friend", responses={204: None})
    def delete(self, request, username):
        SocialService.remove_friend(actor=request.user, target=self.get_target())
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------- block / mute
@extend_schema(tags=["social"])
class BlockView(_TargetUserMixin, APIView):
    @extend_schema(summary="Block a user", responses={201: None})
    def post(self, request, username):
        SocialService.block(actor=request.user, target=self.get_target())
        return Response({"detail": "Blocked."}, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Unblock a user", responses={204: None})
    def delete(self, request, username):
        SocialService.unblock(actor=request.user, target=self.get_target())
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["social"])
class MuteView(_TargetUserMixin, APIView):
    @extend_schema(summary="Mute a user", request=MuteCreateSerializer, responses={201: None})
    def post(self, request, username):
        serializer = MuteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SocialService.mute(
            actor=request.user,
            target=self.get_target(),
            until=serializer.validated_data.get("until"),
        )
        return Response({"detail": "Muted."}, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Unmute a user", responses={204: None})
    def delete(self, request, username):
        SocialService.unmute(actor=request.user, target=self.get_target())
        return Response(status=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------------- lists
@extend_schema(tags=["social"])
class FollowersView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PublicUserSerializer

    def get_queryset(self):
        return User.objects.filter(following_set__following=self.request.user).select_related(
            "profile"
        )


@extend_schema(tags=["social"])
class FollowingView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PublicUserSerializer

    def get_queryset(self):
        return User.objects.filter(follower_set__follower=self.request.user).select_related(
            "profile"
        )


@extend_schema(tags=["social"])
class FriendsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PublicUserSerializer

    def get_queryset(self):
        me = self.request.user
        friend_ids = set(
            Friendship.objects.filter(Q(user_low=me) | Q(user_high=me)).values_list(
                "user_low_id", "user_high_id"
            )
        )
        ids = {uid for pair in friend_ids for uid in pair if uid != me.id}
        return User.objects.filter(pk__in=ids).select_related("profile")


@extend_schema(tags=["social"])
class IncomingFriendRequestsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    def get_queryset(self):
        return FriendRequest.objects.filter(
            to_user=self.request.user, status=FriendRequestStatus.PENDING
        ).select_related("from_user__profile", "to_user__profile")


@extend_schema(tags=["social"])
class OutgoingFriendRequestsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    def get_queryset(self):
        return FriendRequest.objects.filter(
            from_user=self.request.user, status=FriendRequestStatus.PENDING
        ).select_related("from_user__profile", "to_user__profile")


@extend_schema(tags=["social"])
class BlockedListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BlockSerializer

    def get_queryset(self):
        return Block.objects.filter(blocker=self.request.user).select_related("blocked__profile")


@extend_schema(tags=["social"])
class MutedListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MuteSerializer

    def get_queryset(self):
        return Mute.objects.filter(muter=self.request.user).select_related("muted__profile")
