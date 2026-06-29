from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


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
