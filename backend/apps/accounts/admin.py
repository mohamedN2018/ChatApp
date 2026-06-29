from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import OneTimeToken, SecurityEvent, User, UserSession


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = (
        "username",
        "email",
        "display_name",
        "is_active",
        "is_email_verified",
        "is_verified",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_active", "is_email_verified", "is_verified", "is_staff", "is_superuser")
    search_fields = ("username", "email", "display_name")
    readonly_fields = ("id", "last_login", "created_at", "updated_at", "last_seen_at", "deleted_at")

    fieldsets = (
        (None, {"fields": ("id", "email", "username", "password")}),
        (_("Profile"), {"fields": ("display_name",)}),
        (
            _("Status"),
            {
                "fields": (
                    "is_active",
                    "is_email_verified",
                    "is_verified",
                    "last_seen_at",
                    "deleted_at",
                )
            },
        ),
        (_("Permissions"), {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )


@admin.register(OneTimeToken)
class OneTimeTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "purpose", "expires_at", "consumed_at", "created_at")
    list_filter = ("purpose",)
    search_fields = ("user__email", "user__username")
    readonly_fields = (
        "id",
        "user",
        "purpose",
        "token_hash",
        "expires_at",
        "consumed_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "device_label",
        "ip_address",
        "last_used_at",
        "expires_at",
        "revoked_at",
    )
    list_filter = ("revoked_at",)
    search_fields = ("user__email", "user__username", "ip_address", "device_label")
    readonly_fields = (
        "id",
        "user",
        "device_label",
        "user_agent",
        "ip_address",
        "last_used_at",
        "expires_at",
        "revoked_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-last_used_at",)

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "event_type", "ip_address", "created_at")
    list_filter = ("event_type",)
    search_fields = ("user__email", "user__username", "ip_address")
    readonly_fields = (
        "id",
        "user",
        "event_type",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        return False
