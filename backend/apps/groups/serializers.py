"""Serializers for groups, channels, members, and invites."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.fileserve import signed_file_url
from apps.profiles.serializers import PublicUserSerializer

from .models import Channel, ChannelType, Group, GroupInvite, GroupMembership, GroupRole


class ChannelSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = Channel
        fields = (
            "id",
            "name",
            "type",
            "topic",
            "is_private",
            "is_readonly",
            "position",
            "conversation_id",
            "created_at",
        )
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    owner = PublicUserSerializer(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "banner_url",
            "owner",
            "is_public",
            "max_members",
            "member_count",
            "my_role",
            "created_at",
        )
        read_only_fields = fields

    def get_avatar_url(self, obj) -> str | None:
        return signed_file_url(obj.avatar)

    def get_banner_url(self, obj) -> str | None:
        return signed_file_url(obj.banner)

    def get_my_role(self, obj) -> str | None:
        viewer = self.context["request"].user
        membership = next((m for m in obj.memberships.all() if m.user_id == viewer.id), None)
        return membership.role if membership else None


class GroupDetailSerializer(GroupSerializer):
    channels = serializers.SerializerMethodField()

    class Meta(GroupSerializer.Meta):
        fields = (*GroupSerializer.Meta.fields, "channels")

    def get_channels(self, obj) -> list:
        viewer = self.context["request"].user
        is_member = obj.memberships.filter(user=viewer).exists()
        channels = obj.channels.all() if is_member else obj.channels.filter(is_private=False)
        return ChannelSerializer(channels, many=True).data


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_public = serializers.BooleanField(required=False, default=False)
    max_members = serializers.IntegerField(required=False, allow_null=True, min_value=2)


class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("name", "description", "is_public", "max_members")


class ChannelCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=ChannelType.choices, default=ChannelType.TEXT)
    topic = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    is_private = serializers.BooleanField(required=False, default=False)


class MemberSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = ("id", "user", "role", "nickname", "joined_at")
        read_only_fields = fields


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[r for r in GroupRole.choices if r[0] != "owner"])


class InviteSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = GroupInvite
        fields = ("id", "code", "expires_at", "max_uses", "uses", "is_valid", "created_at")
        read_only_fields = fields


class CreateInviteSerializer(serializers.Serializer):
    expires_in_hours = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    max_uses = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class JoinInviteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
