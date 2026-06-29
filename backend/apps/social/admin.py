from __future__ import annotations

from django.contrib import admin

from .models import Block, Follow, FriendRequest, Friendship, Mute


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")
    raw_id_fields = ("follower", "following")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("from_user__username", "to_user__username")
    raw_id_fields = ("from_user", "to_user")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("user_low", "user_high", "created_at")
    search_fields = ("user_low__username", "user_high__username")
    raw_id_fields = ("user_low", "user_high")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    raw_id_fields = ("blocker", "blocked")


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("muter", "muted", "until", "created_at")
    search_fields = ("muter__username", "muted__username")
    raw_id_fields = ("muter", "muted")
