"""
Media service layer: direct uploads, chunked/resumable uploads, and access
control.

Chunked assembly currently buffers the file in memory while concatenating chunks
— fine for the sizes a chat handles; for very large files this would move to S3
multipart upload. The trade-off is intentional and isolated here.
"""

from __future__ import annotations

import contextlib
import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.exceptions import ValidationError

from .models import MediaFile, UploadSession, UploadStatus
from .tasks import process_media_task


class MediaService:
    # ------------------------------------------------------------- direct upload
    @staticmethod
    def create_from_file(
        *, owner, django_file, filename=None, content_type=None, kind=None
    ) -> MediaFile:
        filename = (filename or getattr(django_file, "name", "file"))[:255]
        content_type = (content_type or getattr(django_file, "content_type", "") or "")[:150]
        media = MediaFile(
            owner=owner,
            kind=kind or MediaFile.kind_for_content_type(content_type, filename),
            original_filename=filename,
            content_type=content_type,
        )
        media.file.save(filename, django_file, save=False)
        media.size = media.file.size
        media.save()
        process_media_task.delay(str(media.id))
        return media

    # ------------------------------------------------------------ chunked upload
    @staticmethod
    def start_session(*, owner, filename, content_type, total_size, total_chunks) -> UploadSession:
        if total_chunks < 1:
            raise ValidationError("total_chunks must be >= 1.")
        return UploadSession.objects.create(
            owner=owner,
            filename=filename[:255],
            content_type=(content_type or "")[:150],
            total_size=total_size,
            total_chunks=total_chunks,
        )

    @staticmethod
    def store_chunk(*, session: UploadSession, index: int, data: bytes) -> None:
        if session.status != UploadStatus.PENDING:
            raise ValidationError("This upload session is not active.")
        if not (0 <= index < session.total_chunks):
            raise ValidationError("Chunk index out of range.")
        key = session.chunk_key(index)
        if default_storage.exists(key):
            default_storage.delete(key)
        default_storage.save(key, ContentFile(data))
        if index not in session.received_chunks:
            session.received_chunks = sorted(set(session.received_chunks) | {index})
            session.save(update_fields=["received_chunks", "updated_at"])

    @classmethod
    def complete_session(cls, *, session: UploadSession) -> MediaFile:
        if session.status == UploadStatus.COMPLETED and session.media_id:
            return session.media
        if not session.is_complete:
            received = len(set(session.received_chunks))
            raise ValidationError(
                f"Upload incomplete: {received}/{session.total_chunks} chunks received."
            )
        buffer = io.BytesIO()
        for index in range(session.total_chunks):
            with default_storage.open(session.chunk_key(index), "rb") as fh:
                buffer.write(fh.read())
        media = MediaFile(
            owner=session.owner,
            kind=MediaFile.kind_for_content_type(session.content_type, session.filename),
            original_filename=session.filename[:255],
            content_type=session.content_type,
        )
        media.file.save(session.filename, ContentFile(buffer.getvalue()), save=False)
        media.size = media.file.size
        media.save()

        for index in range(session.total_chunks):
            with contextlib.suppress(Exception):
                default_storage.delete(session.chunk_key(index))

        session.status = UploadStatus.COMPLETED
        session.media = media
        session.save(update_fields=["status", "media", "updated_at"])

        process_media_task.delay(str(media.id))
        return media

    @staticmethod
    def abort_session(*, session: UploadSession) -> None:
        for index in range(session.total_chunks):
            with contextlib.suppress(Exception):
                default_storage.delete(session.chunk_key(index))
        session.status = UploadStatus.ABORTED
        session.save(update_fields=["status", "updated_at"])

    # ----------------------------------------------------------------- access
    @staticmethod
    def can_access(user, media: MediaFile) -> bool:
        if media.owner_id == user.id:
            return True
        # Accessible if attached to a message in a conversation the user is in.
        from apps.chat.models import MessageAttachment

        return MessageAttachment.objects.filter(
            media=media,
            message__conversation__participants__user=user,
            message__conversation__participants__left_at__isnull=True,
        ).exists()
