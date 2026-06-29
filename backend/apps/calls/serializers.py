"""Serializers for calls and call participants."""

from __future__ import annotations

from rest_framework import serializers

from apps.profiles.serializers import PublicUserSerializer

from .models import Call, CallParticipant, CallType


class CallParticipantSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = CallParticipant
        fields = (
            "id",
            "user",
            "state",
            "is_muted",
            "is_video_on",
            "hand_raised",
            "joined_at",
            "left_at",
        )
        read_only_fields = fields


class CallSerializer(serializers.ModelSerializer):
    initiator = PublicUserSerializer(read_only=True)
    participants = CallParticipantSerializer(many=True, read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = Call
        fields = (
            "id",
            "conversation",
            "initiator",
            "type",
            "status",
            "started_at",
            "ended_at",
            "duration_seconds",
            "participants",
            "created_at",
        )
        read_only_fields = fields


class InitiateCallSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=CallType.choices, default=CallType.AUDIO)
