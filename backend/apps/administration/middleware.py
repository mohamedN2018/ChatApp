"""
Hardening middleware.

* MaintenanceModeMiddleware — when maintenance mode is on, returns 503 for normal
  traffic while always allowing health checks, the admin API (so admins can turn
  it back off), Django admin, docs, and login/token endpoints.
* UserLanguageMiddleware — lets clients force a UI language per request via the
  ``X-Language`` header (falls back to Django's Accept-Language negotiation),
  enabling Arabic/English (and RTL on the client) without round-tripping a cookie.
"""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.utils import translation

# Paths that must keep working during maintenance.
_MAINTENANCE_ALLOWLIST = (
    "/health",
    "/admin/",  # Django session admin
    "/api/schema",
    "/api/docs",
    "/api/redoc",
    "/api/v1/admin/",  # admin REST API (IsAdminUser-protected)
    "/api/v1/accounts/login",
    "/api/v1/accounts/token",
)


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._blocked(request):
            from .models import SystemConfig

            return JsonResponse(
                {
                    "error": {
                        "type": "maintenance",
                        "message": SystemConfig.get_solo().maintenance_message,
                        "status_code": 503,
                    }
                },
                status=503,
            )
        return self.get_response(request)

    @staticmethod
    def _blocked(request) -> bool:
        path = request.path
        if any(path.startswith(prefix) for prefix in _MAINTENANCE_ALLOWLIST):
            return False
        # Staff sessions bypass (token-authed admins use the allowlisted admin API).
        if getattr(request.user, "is_staff", False):
            return False
        from .models import SystemConfig

        return SystemConfig.get_solo().maintenance_mode


class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        requested = request.headers.get("X-Language")
        if requested in self._supported:
            translation.activate(requested)
            request.LANGUAGE_CODE = requested
        response = self.get_response(request)
        if requested in self._supported:
            response.headers.setdefault("Content-Language", requested)
        return response
