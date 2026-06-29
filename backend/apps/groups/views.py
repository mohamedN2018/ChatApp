"""Group, channel, membership, and invite endpoints."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.images import process_image

from .models import Channel, Group, GroupRole
from .serializers import (
    ChangeRoleSerializer,
    ChannelCreateSerializer,
    ChannelSerializer,
    CreateInviteSerializer,
    GroupCreateSerializer,
    GroupDetailSerializer,
    GroupSerializer,
    GroupUpdateSerializer,
    InviteSerializer,
    JoinInviteSerializer,
    MemberSerializer,
)
from .services import GroupService

User = get_user_model()


def get_group(slug) -> Group:
    return get_object_or_404(Group, slug=slug)


def viewable_or_404(group, user) -> Group:
    if not group.is_public and not GroupService.membership(group, user):
        raise NotFound()
    return group


# --------------------------------------------------------------------- groups
@extend_schema(tags=["groups"])
class GroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=GroupSerializer(many=True), summary="List my groups")
    def get(self, request):
        groups = (
            Group.objects.filter(memberships__user=request.user)
            .prefetch_related("memberships")
            .distinct()
        )
        return Response(GroupSerializer(groups, many=True, context={"request": request}).data)

    @extend_schema(request=GroupCreateSerializer, responses=GroupDetailSerializer)
    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = GroupService.create_group(owner=request.user, **serializer.validated_data)
        return Response(
            GroupDetailSerializer(group, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["groups"])
class GroupDiscoverView(ListAPIView):
    """Public groups, optionally filtered by ?search=."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupSerializer

    def get_queryset(self):
        qs = Group.objects.filter(is_public=True).prefetch_related("memberships")
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs


@extend_schema(tags=["groups"])
class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=GroupDetailSerializer)
    def get(self, request, slug):
        group = viewable_or_404(get_group(slug), request.user)
        return Response(GroupDetailSerializer(group, context={"request": request}).data)

    @extend_schema(request=GroupUpdateSerializer, responses=GroupSerializer)
    def patch(self, request, slug):
        group = get_group(slug)
        GroupService._require(group, request.user, GroupRole.ADMIN)
        serializer = GroupUpdateSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GroupSerializer(group, context={"request": request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, slug):
        GroupService.delete_group(actor=request.user, group=get_group(slug))
        return Response(status=status.HTTP_204_NO_CONTENT)


class _GroupImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    field_name = ""
    max_size = (1024, 1024)

    @extend_schema(tags=["groups"], responses=GroupSerializer)
    def post(self, request, slug):
        group = get_group(slug)
        GroupService._require(group, request.user, GroupRole.ADMIN)
        upload = request.FILES.get("image")
        if upload is None:
            return Response({"detail": "Missing 'image'."}, status=400)
        try:
            processed = process_image(upload, max_size=self.max_size, output_format="WEBP")
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"image": exc.messages}) from exc
        getattr(group, self.field_name).save(f"{self.field_name}.webp", processed, save=True)
        return Response(GroupSerializer(group, context={"request": request}).data)


class GroupAvatarView(_GroupImageView):
    field_name = "avatar"
    max_size = (512, 512)


class GroupBannerView(_GroupImageView):
    field_name = "banner"
    max_size = (1600, 600)


# --------------------------------------------------------------------- members
@extend_schema(tags=["groups"])
class MemberListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MemberSerializer

    def get_queryset(self):
        group = viewable_or_404(get_group(self.kwargs["slug"]), self.request.user)
        return group.memberships.select_related("user__profile").all()


@extend_schema(tags=["groups"])
class MemberView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangeRoleSerializer, responses=MemberSerializer, summary="Change a member's role"
    )
    def patch(self, request, slug, user_id):
        group = get_group(slug)
        target = get_object_or_404(User, pk=user_id)
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = GroupService.change_role(
            actor=request.user,
            group=group,
            target_user=target,
            role=serializer.validated_data["role"],
        )
        return Response(MemberSerializer(membership).data)

    @extend_schema(responses={204: None}, summary="Remove (kick) a member")
    def delete(self, request, slug, user_id):
        group = get_group(slug)
        target = get_object_or_404(User, pk=user_id)
        GroupService.remove_member(actor=request.user, group=group, target_user=target)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["groups"])
class LeaveGroupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def post(self, request, slug):
        GroupService.leave_group(user=request.user, group=get_group(slug))
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["groups"])
class TransferOwnershipView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Transfer group ownership", responses={204: None})
    def post(self, request, slug):
        target = get_object_or_404(User, pk=request.data.get("user_id"))
        GroupService.transfer_ownership(
            actor=request.user, group=get_group(slug), target_user=target
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------- channels
@extend_schema(tags=["groups"])
class ChannelListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ChannelSerializer(many=True))
    def get(self, request, slug):
        group = viewable_or_404(get_group(slug), request.user)
        is_member = GroupService.membership(group, request.user) is not None
        channels = group.channels.all() if is_member else group.channels.filter(is_private=False)
        return Response(ChannelSerializer(channels, many=True).data)

    @extend_schema(request=ChannelCreateSerializer, responses=ChannelSerializer)
    def post(self, request, slug):
        group = get_group(slug)
        serializer = ChannelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        channel = GroupService.create_channel(
            actor=request.user,
            group=group,
            name=data["name"],
            channel_type=data["type"],
            topic=data["topic"],
            is_private=data["is_private"],
        )
        return Response(ChannelSerializer(channel).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["groups"])
class ChannelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, slug, channel_id):
        channel = get_object_or_404(Channel, pk=channel_id, group__slug=slug)
        GroupService.delete_channel(actor=request.user, channel=channel)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------- invites
@extend_schema(tags=["groups"])
class InviteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=InviteSerializer(many=True))
    def get(self, request, slug):
        group = get_group(slug)
        GroupService._require(group, request.user, GroupRole.MODERATOR)
        return Response(InviteSerializer(group.invites.filter(is_active=True), many=True).data)

    @extend_schema(request=CreateInviteSerializer, responses=InviteSerializer)
    def post(self, request, slug):
        group = get_group(slug)
        serializer = CreateInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hours = serializer.validated_data.get("expires_in_hours")
        invite = GroupService.create_invite(
            actor=request.user,
            group=group,
            expires_in=timedelta(hours=hours) if hours else None,
            max_uses=serializer.validated_data.get("max_uses"),
        )
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["groups"])
class JoinByInviteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=JoinInviteSerializer, responses=GroupDetailSerializer)
    def post(self, request):
        serializer = JoinInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = GroupService.join_via_invite(
            user=request.user, code=serializer.validated_data["code"]
        )
        return Response(GroupDetailSerializer(group, context={"request": request}).data)


@extend_schema(tags=["groups"])
class JoinPublicView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=GroupDetailSerializer, summary="Join a public group")
    def post(self, request, slug):
        group = get_group(slug)
        GroupService.join_public(user=request.user, group=group)
        return Response(GroupDetailSerializer(group, context={"request": request}).data)
