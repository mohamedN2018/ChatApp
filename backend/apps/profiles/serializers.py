"""Serializers for profiles, privacy, and notification settings."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.fileserve import signed_file_url
from apps.social.services import SocialService

from .models import NotificationSettings, PrivacySettings, Profile


class PublicUserSerializer(serializers.Serializer):
    """Compact user card embedded in lists (followers, friends, search…)."""

    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, user) -> str | None:
        profile = getattr(user, "profile", None)
        return signed_file_url(profile.avatar) if profile else None


class ProfileSerializer(serializers.ModelSerializer):
    """Full profile view, including viewer-relative relationship state."""

    user = PublicUserSerializer(read_only=True)
    avatar = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    relationship = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "user",
            "avatar",
            "cover",
            "bio",
            "country",
            "language",
            "website",
            "birthday",
            "social_links",
            "status",
            "custom_status_text",
            "custom_status_emoji",
            "followers_count",
            "following_count",
            "relationship",
        )
        read_only_fields = fields

    def get_avatar(self, obj) -> str | None:
        return signed_file_url(obj.avatar)

    def get_cover(self, obj) -> str | None:
        return signed_file_url(obj.cover)

    def get_followers_count(self, obj) -> int:
        return obj.user.follower_set.count()

    def get_following_count(self, obj) -> int:
        return obj.user.following_set.count()

    def get_relationship(self, obj) -> dict | None:
        viewer = self.context["request"].user
        if not viewer.is_authenticated or viewer == obj.user:
            return None
        return {
            "is_following": SocialService.is_following(viewer, obj.user),
            "is_followed_by": SocialService.is_following(obj.user, viewer),
            "is_friend": SocialService.are_friends(viewer, obj.user),
            "is_blocked": SocialService.is_blocked_between(viewer, obj.user),
        }


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Editable profile fields (avatar/cover handled by dedicated upload views)."""

    class Meta:
        model = Profile
        fields = (
            "bio",
            "country",
            "language",
            "website",
            "birthday",
            "social_links",
            "status",
            "custom_status_text",
            "custom_status_emoji",
        )

    def validate_social_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("social_links must be an object.")
        if len(value) > 20:
            raise serializers.ValidationError("Too many social links (max 20).")
        return value


class PrivacySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacySettings
        exclude = ("id", "user", "created_at", "updated_at")


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        exclude = ("id", "user", "created_at", "updated_at")


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
