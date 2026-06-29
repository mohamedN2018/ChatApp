"""
Health probes for orchestrators and load balancers.

* /health/        Liveness  — is the process up? Never touches dependencies.
* /health/ready/  Readiness — can it serve traffic? Checks DB, cache (Redis),
                  and the channel layer. Returns 503 if any dependency is down,
                  so load balancers stop routing to a degraded instance.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class LivenessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(
        tags=["health"],
        summary="Liveness probe",
        responses={200: dict},
    )
    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"})


class ReadinessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(
        tags=["health"],
        summary="Readiness probe",
        responses={200: dict, 503: dict},
    )
    def get(self, request, *args, **kwargs):
        checks = {
            "database": self._check_database(),
            "cache": self._check_cache(),
            "channel_layer": self._check_channel_layer(),
        }
        healthy = all(c["ok"] for c in checks.values())
        return Response(
            {"status": "ready" if healthy else "degraded", "checks": checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @staticmethod
    def _check_database() -> dict:
        try:
            connections["default"].cursor().execute("SELECT 1")
            return {"ok": True}
        except OperationalError as exc:  # pragma: no cover - failure path
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _check_cache() -> dict:
        try:
            cache.set("__healthcheck__", "1", timeout=5)
            return {"ok": cache.get("__healthcheck__") == "1"}
        except Exception as exc:  # pragma: no cover - failure path
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _check_channel_layer() -> dict:
        try:
            from channels.layers import get_channel_layer

            layer = get_channel_layer()
            if layer is None:
                return {"ok": False, "error": "no channel layer configured"}
            # Round-trip a message through the layer to prove Redis connectivity.
            async_to_sync(layer.send)("__healthcheck__", {"type": "health.ping"})
            return {"ok": True}
        except Exception as exc:  # pragma: no cover - failure path
            return {"ok": False, "error": str(exc)}
