from __future__ import annotations

from django.contrib import admin

from .models import Channel, Group, GroupInvite, GroupMembership


class MembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    raw_id_fields = ("user",)


class ChannelInline(admin.TabularInline):
    model = Channel
    extra = 0
    raw_id_fields = ("conversation",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "is_public", "created_at")
    list_filter = ("is_public",)
    search_fields = ("name", "slug")
    raw_id_fields = ("owner",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ChannelInline, MembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("group__name", "user__username")
    raw_id_fields = ("group", "user")


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "type", "is_private", "position")
    list_filter = ("type", "is_private")
    search_fields = ("name", "group__name")
    raw_id_fields = ("group", "conversation")


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ("code", "group", "created_by", "uses", "max_uses", "expires_at", "is_active")
    search_fields = ("code", "group__name")
    raw_id_fields = ("group", "created_by")
