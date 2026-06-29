"""
Root URL configuration.

REST endpoints are versioned under /api/v1/. WebSocket routes live in
config/asgi.py (Channels), not here. Schema/docs and health checks are mounted
at the top level.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.common.views import LivenessView, ReadinessView

# --- API v1 -----------------------------------------------------------------
api_v1_patterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("social/", include("apps.social.urls")),
    path("presence/", include("apps.realtime.urls")),
    path("chat/", include("apps.chat.urls")),
    path("media/", include("apps.media.urls")),
    path("groups/", include("apps.groups.urls")),
    path("calls/", include("apps.calls.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # Health probes (used by Docker/K8s and load balancers).
    path("health/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    # API schema & interactive docs.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Versioned API.
    path("api/v1/", include((api_v1_patterns, "v1"), namespace="v1")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
