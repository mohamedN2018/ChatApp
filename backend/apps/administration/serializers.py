"""Serializers for administration & moderation."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.profiles.serializers import PublicUserSerializer

from .models import (
    AdminAuditLog,
    Announcement,
    FeatureFlag,
    Report,
    ReportTargetType,
    SystemConfig,
)

User = get_user_model()


class ReportSerializer(serializers.ModelSerializer):
    reporter = PublicUserSerializer(read_only=True)
    handled_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = Report
        fields = (
            "id",
            "reporter",
            "target_type",
            "target_id",
            "reason",
            "details",
            "status",
            "handled_by",
            "resolution_notes",
            "created_at",
        )
        read_only_fields = fields


class ReportCreateSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=ReportTargetType.choices)
    target_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=60)
    details = serializers.CharField(required=False, allow_blank=True, default="")


class ReportUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Report._meta.get_field("status").choices)
    resolution_notes = serializers.CharField(required=False, allow_blank=True, default="")


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ("id", "key", "description", "is_enabled", "updated_at")
        read_only_fields = ("id", "updated_at")


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "level", "is_active", "starts_at", "ends_at", "created_at")
        read_only_fields = ("id", "created_at")


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ("maintenance_mode", "maintenance_message", "signups_enabled", "updated_at")
        read_only_fields = ("updated_at",)


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = ("id", "actor", "action", "target", "metadata", "ip_address", "created_at")
        read_only_fields = fields


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "display_name",
            "is_active",
            "is_email_verified",
            "is_verified",
            "is_staff",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "email", "username", "created_at", "last_seen_at")


class AdminUserUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_verified = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
