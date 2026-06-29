"""Profile, privacy, and notification-settings endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.images import process_image
from apps.social.services import SocialService

from .models import Profile, Visibility
from .serializers import (
    ImageUploadSerializer,
    NotificationSettingsSerializer,
    PrivacySettingsSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
)

AVATAR_SIZE = (512, 512)
COVER_SIZE = (1600, 600)


@extend_schema(tags=["profiles"])
class MeProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.profile

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return ProfileSerializer


@extend_schema(tags=["profiles"])
class PublicProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer

    def get_object(self):
        profile = get_object_or_404(
            Profile.objects.select_related("user", "user__privacy"),
            user__username=self.kwargs["username"],
        )
        viewer, owner = self.request.user, profile.user
        if viewer != owner:
            # Blocked either way -> pretend the profile doesn't exist.
            if SocialService.is_blocked_between(viewer, owner):
                raise NotFound()
            vis = owner.privacy.profile_visibility
            if vis == Visibility.NOBODY or (
                vis == Visibility.FRIENDS and not SocialService.are_friends(viewer, owner)
            ):
                raise PermissionDenied("This profile is private.")
        return profile


class _ImageUploadView(APIView):
    """Shared avatar/cover upload handling (validate -> Pillow -> store)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    field_name = ""
    max_size = (512, 512)

    @extend_schema(tags=["profiles"], request=ImageUploadSerializer, responses=ProfileSerializer)
    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            processed = process_image(
                serializer.validated_data["image"], max_size=self.max_size, output_format="WEBP"
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"image": exc.messages}) from exc
        profile = request.user.profile
        getattr(profile, self.field_name).save(
            f"{self.field_name}_{request.user.id}.webp", processed, save=True
        )
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    @extend_schema(tags=["profiles"], responses={204: None})
    def delete(self, request):
        profile = request.user.profile
        field = getattr(profile, self.field_name)
        if field:
            field.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvatarView(_ImageUploadView):
    field_name = "avatar"
    max_size = AVATAR_SIZE


class CoverView(_ImageUploadView):
    field_name = "cover"
    max_size = COVER_SIZE


@extend_schema(tags=["profiles"])
class PrivacySettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PrivacySettingsSerializer

    def get_object(self):
        return self.request.user.privacy


@extend_schema(tags=["profiles"])
class NotificationSettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSettingsSerializer

    def get_object(self):
        return self.request.user.notification_settings
