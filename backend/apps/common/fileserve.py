"""
Generic signed file serving.

User images (avatars, covers, group banners) live in MinIO, whose presigned URLs
use an internal host the browser can't reach. Rather than expose the bucket
publicly, these are streamed through the backend behind a short-lived signed token
over the storage path — usable directly in ``<img src>`` without an auth header.
The token is only embedded in serialized objects the caller is allowed to see.
"""

from __future__ import annotations

import mimetypes

from django.core import signing
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

_SALT = "common.fileserve"
_MAX_AGE = 60 * 60  # 1 hour


def sign_path(name: str) -> str:
    return signing.dumps(name, salt=_SALT)


def signed_file_url(file_field) -> str | None:
    """Return a backend-served, signed URL for a FileField/ImageField (or None)."""
    if not file_field:
        return None
    return f"/api/v1/files/?token={sign_path(file_field.name)}"


class ServeFileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        tags=["media"],
        parameters=[OpenApiParameter("token", str, OpenApiParameter.QUERY)],
        summary="Stream a signed file (avatars, covers, banners)",
    )
    def get(self, request):
        token = request.query_params.get("token", "")
        try:
            name = signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
        except signing.BadSignature as exc:
            raise PermissionDenied("Invalid or expired file link.") from exc
        if not default_storage.exists(name):
            raise Http404()
        ctype = "image/webp" if name.endswith(".webp") else mimetypes.guess_type(name)[0]
        return FileResponse(
            default_storage.open(name, "rb"), content_type=ctype or "application/octet-stream"
        )
