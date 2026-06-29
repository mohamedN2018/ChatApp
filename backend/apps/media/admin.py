from __future__ import annotations

from django.contrib import admin

from .models import MediaFile, UploadSession


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "kind", "original_filename", "size", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("id", "original_filename", "owner__username")
    raw_id_fields = ("owner",)
    readonly_fields = (
        "size",
        "width",
        "height",
        "duration",
        "waveform",
        "created_at",
        "updated_at",
    )


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "filename", "total_chunks", "status", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "filename", "owner__username")
    raw_id_fields = ("owner", "media")
