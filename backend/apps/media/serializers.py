"""Serializers for media files and chunked upload sessions."""

from __future__ import annotations

from rest_framework import serializers

from .models import MediaFile, UploadSession
from .signing import sign_media


class MediaFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaFile
        fields = (
            "id",
            "kind",
            "url",
            "thumbnail_url",
            "original_filename",
            "content_type",
            "size",
            "width",
            "height",
            "duration",
            "waveform",
            "status",
            "created_at",
        )
        read_only_fields = fields

    def get_url(self, obj) -> str | None:
        # Backend-served, signed, browser-usable URL (resolved against the API
        # origin by the client). Avoids MinIO's internal-host presigned URLs.
        if not obj.file:
            return None
        return f"/api/v1/media/{obj.id}/download/?token={sign_media(obj.id)}"

    def get_thumbnail_url(self, obj) -> str | None:
        if not obj.thumbnail:
            return None
        return f"/api/v1/media/{obj.id}/thumbnail/?token={sign_media(obj.id)}"


class DirectUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    # Optional override so the client can mark a recording as a voice note
    # (enables waveform extraction); otherwise the kind is derived from the type.
    kind = serializers.ChoiceField(
        choices=MediaFile._meta.get_field("kind").choices, required=False, allow_null=True
    )


class StartUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    total_size = serializers.IntegerField(min_value=1)
    total_chunks = serializers.IntegerField(min_value=1)


class UploadSessionSerializer(serializers.ModelSerializer):
    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = UploadSession
        fields = (
            "id",
            "filename",
            "content_type",
            "total_size",
            "total_chunks",
            "received_chunks",
            "status",
            "is_complete",
            "expires_at",
            "created_at",
        )
        read_only_fields = fields
