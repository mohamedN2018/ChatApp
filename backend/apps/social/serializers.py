"""Serializers for the social graph (friend requests, blocks, mutes)."""

from __future__ import annotations

from rest_framework import serializers

from apps.profiles.serializers import PublicUserSerializer

from .models import Block, FriendRequest, Mute


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = PublicUserSerializer(read_only=True)
    to_user = PublicUserSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ("id", "from_user", "to_user", "status", "created_at", "responded_at")
        read_only_fields = fields


class BlockSerializer(serializers.ModelSerializer):
    blocked = PublicUserSerializer(read_only=True)

    class Meta:
        model = Block
        fields = ("id", "blocked", "created_at")
        read_only_fields = fields


class MuteSerializer(serializers.ModelSerializer):
    muted = PublicUserSerializer(read_only=True)

    class Meta:
        model = Mute
        fields = ("id", "muted", "until", "created_at")
        read_only_fields = fields


class MuteCreateSerializer(serializers.Serializer):
    until = serializers.DateTimeField(required=False, allow_null=True)
