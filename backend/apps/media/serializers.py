"""Serializers for media files and chunked upload sessions."""

from __future__ import annotations

from rest_framework import serializers

from .models import MediaFile, UploadSession


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
        return obj.file.url if obj.file else None

    def get_thumbnail_url(self, obj) -> str | None:
        return obj.thumbnail.url if obj.thumbnail else None


class DirectUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


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
