from __future__ import annotations

from django.contrib import admin

from .models import AdminAuditLog, Announcement, FeatureFlag, Report, SystemConfig


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "target_type", "reason", "status", "reporter", "created_at")
    list_filter = ("status", "target_type")
    search_fields = ("reason", "details", "reporter__username")
    raw_id_fields = ("reporter", "handled_by")
    date_hierarchy = "created_at"


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "is_enabled", "description", "updated_at")
    list_filter = ("is_enabled",)
    search_fields = ("key",)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "is_active", "starts_at", "ends_at")
    list_filter = ("level", "is_active")
    search_fields = ("title", "body")


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ("maintenance_mode", "signups_enabled", "updated_at")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "target", "actor__username")
    date_hierarchy = "created_at"
