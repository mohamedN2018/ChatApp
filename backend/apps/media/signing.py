"""
Capability tokens for media delivery.

Media is served through the backend (not via raw MinIO presigned URLs, whose host
differs inside the container vs. the browser). A short-lived signed token grants
access to one media file so it can be used directly in ``<img src>`` / ``<a href>``
without an Authorization header. The token is only ever embedded in a serialized
MediaFile, which is itself only returned to users allowed to see that media.
"""

from __future__ import annotations

from django.core import signing

_SALT = "media.access"
DEFAULT_MAX_AGE = 60 * 60  # 1 hour


def sign_media(media_id) -> str:
    return signing.dumps(str(media_id), salt=_SALT)


def unsign_media(token: str, max_age: int = DEFAULT_MAX_AGE) -> str | None:
    try:
        return signing.loads(token, salt=_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
