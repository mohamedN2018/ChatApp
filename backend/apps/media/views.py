"""
Media endpoints: direct upload, chunked upload (init/chunk/complete/abort/status),
and access-controlled retrieval.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MediaFile, UploadSession
from .serializers import (
    DirectUploadSerializer,
    MediaFileSerializer,
    StartUploadSerializer,
    UploadSessionSerializer,
)
from .services import MediaService

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
