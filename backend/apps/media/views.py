"""
Media endpoints: direct upload, chunked upload (init/chunk/complete/abort/status),
and access-controlled retrieval.
"""

from __future__ import annotations

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MediaFile, MediaKind, UploadSession
from .serializers import (
    DirectUploadSerializer,
    MediaFileSerializer,
    StartUploadSerializer,
    UploadSessionSerializer,
)
from .services import MediaService
from .signing import unsign_media

MAX_DIRECT_UPLOAD = 25 * 1024 * 1024  # 25 MB — larger files use chunked upload


@extend_schema(tags=["media"])
class DirectUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=DirectUploadSerializer, responses=MediaFileSerializer)
    def post(self, request):
        serializer = DirectUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        if upload.size > MAX_DIRECT_UPLOAD:
            return Response(
                {"detail": "File too large for direct upload; use the chunked upload endpoints."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        media = MediaService.create_from_file(owner=request.user, django_file=upload)
        return Response(
            MediaFileSerializer(media, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["media"])
class MediaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MediaFileSerializer)
    def get(self, request, media_id):
        media = get_object_or_404(MediaFile, pk=media_id)
        if not MediaService.can_access(request.user, media):
            raise PermissionDenied("You do not have access to this file.")
        return Response(MediaFileSerializer(media, context={"request": request}).data)


_INLINE_KINDS = {MediaKind.IMAGE, MediaKind.VIDEO, MediaKind.AUDIO, MediaKind.VOICE}


class _MediaServeView(APIView):
    """Stream a media blob through the backend, authorised by a signed token in
    the query string (so it works in <img>/<a> without an auth header)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    field = "file"

    @extend_schema(
        tags=["media"], parameters=[OpenApiParameter("token", str, OpenApiParameter.QUERY)]
    )
    def get(self, request, media_id):
        if unsign_media(request.query_params.get("token", "")) != str(media_id):
            raise PermissionDenied("Invalid or expired media link.")
        media = get_object_or_404(MediaFile, pk=media_id)
        file_field = getattr(media, self.field)
        if not file_field:
            raise Http404()
        is_thumb = self.field == "thumbnail"
        content_type = (
            "image/webp" if is_thumb else (media.content_type or "application/octet-stream")
        )
        response = FileResponse(file_field.open("rb"), content_type=content_type)
        disposition = "inline" if (is_thumb or media.kind in _INLINE_KINDS) else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{media.original_filename}"'
        return response


class MediaDownloadView(_MediaServeView):
    field = "file"


class MediaThumbnailView(_MediaServeView):
    field = "thumbnail"


@extend_schema(tags=["media"])
class MediaListView(ListAPIView):
    """The caller's own uploaded media."""

    permission_classes = [IsAuthenticated]
    serializer_class = MediaFileSerializer

    def get_queryset(self):
        return MediaFile.objects.filter(owner=self.request.user)


# ---------------------------------------------------------------- chunked upload
@extend_schema(tags=["media"])
class StartUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=StartUploadSerializer, responses=UploadSessionSerializer)
    def post(self, request):
        serializer = StartUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = MediaService.start_session(owner=request.user, **serializer.validated_data)
        return Response(UploadSessionSerializer(session).data, status=status.HTTP_201_CREATED)


def _own_session(request, upload_id) -> UploadSession:
    session = get_object_or_404(UploadSession, pk=upload_id)
    if session.owner_id != request.user.id:
        raise PermissionDenied("Not your upload session.")
    return session


@extend_schema(tags=["media"])
class UploadChunkView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        parameters=[OpenApiParameter("index", int, OpenApiParameter.PATH)],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"chunk": {"type": "string", "format": "binary"}},
            }
        },
        responses=UploadSessionSerializer,
        summary="Upload one chunk (multipart field 'chunk')",
    )
    def put(self, request, upload_id, index):
        session = _own_session(request, upload_id)
        chunk = request.FILES.get("chunk") or request.data.get("chunk")
        if chunk is None:
            return Response({"detail": "Missing 'chunk'."}, status=status.HTTP_400_BAD_REQUEST)
        MediaService.store_chunk(session=session, index=int(index), data=chunk.read())
        session.refresh_from_db()
        return Response(UploadSessionSerializer(session).data)


@extend_schema(tags=["media"])
class CompleteUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MediaFileSerializer, summary="Assemble chunks into a media file")
    def post(self, request, upload_id):
        session = _own_session(request, upload_id)
        media = MediaService.complete_session(session=session)
        return Response(
            MediaFileSerializer(media, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["media"])
class UploadSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UploadSessionSerializer, summary="Upload session status (for resume)")
    def get(self, request, upload_id):
        return Response(UploadSessionSerializer(_own_session(request, upload_id)).data)

    @extend_schema(responses={204: None}, summary="Abort an upload session")
    def delete(self, request, upload_id):
        MediaService.abort_session(session=_own_session(request, upload_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
