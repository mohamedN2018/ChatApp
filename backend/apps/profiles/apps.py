from __future__ import annotations

from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profiles"
    verbose_name = "Profiles"

    def ready(self) -> None:
        # Register signal handlers (auto-create profile/settings on user creation).
        from . import signals  # noqa: F401
