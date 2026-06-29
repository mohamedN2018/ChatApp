"""
Media post-processing.

Runs in Celery off the request path. Images use Pillow (always available);
video/audio use FFmpeg/ffprobe when present (they are in the container image) and
degrade gracefully to "ready without extras" when not (e.g. local test runs).

  * image -> dimensions + WebP thumbnail
  * video -> dimensions + duration + poster-frame thumbnail
  * audio -> duration; voice notes additionally get a downsampled waveform
"""

from __future__ import annotations

import array
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import MediaFile, MediaKind, MediaStatus

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
THUMB_MAX = (640, 640)
WAVEFORM_BUCKETS = 64


def ffmpeg_available() -> bool:
    return bool(FFMPEG and FFPROBE)


def process_media(media: MediaFile) -> None:
    """Extract metadata + thumbnail for a media file, advancing its status."""
    media.status = MediaStatus.PROCESSING
    media.save(update_fields=["status", "updated_at"])
    try:
        if media.kind == MediaKind.IMAGE:
            _process_image(media)
        elif media.kind == MediaKind.VIDEO:
            _process_video(media)
        elif media.kind in (MediaKind.AUDIO, MediaKind.VOICE):
            _process_audio(media)
        media.status = MediaStatus.READY
        media.save()
    except Exception:
        media.status = MediaStatus.FAILED
        media.save(update_fields=["status", "updated_at"])
        raise


# ------------------------------------------------------------------------- image
def _process_image(media: MediaFile) -> None:
    with media.file.open("rb") as fh:
        image = ImageOps.exif_transpose(Image.open(fh))
        image.load()
    media.width, media.height = image.size

    thumb = image.copy()
    if thumb.mode in ("RGBA", "P", "LA"):
        thumb = thumb.convert("RGB")
    thumb.thumbnail(THUMB_MAX, Image.LANCZOS)
    buffer = io.BytesIO()
    thumb.save(buffer, format="WEBP", quality=80, optimize=True)
    media.thumbnail.save("thumb.webp", ContentFile(buffer.getvalue()), save=False)


# ------------------------------------------------------------------ video / audio
@contextlib.contextmanager
def _local_copy(media: MediaFile):
    """FFmpeg needs a real file; stream the stored object to a temp path."""
    suffix = os.path.splitext(media.original_filename)[1]
    # Keep the temp file by path (not as a context manager): FFmpeg/ffprobe read
    # it as a separate process, and on Windows it can't be open simultaneously.
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)  # noqa: SIM115
    try:
        with media.file.open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                tmp.write(chunk)
        tmp.close()
        yield tmp.name
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp.name)


def _ffprobe(path: str) -> dict:
    result = subprocess.run(
        [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return json.loads(result.stdout or "{}")


def _process_video(media: MediaFile) -> None:
    if not ffmpeg_available():
        return
    with _local_copy(media) as path:
        info = _ffprobe(path)
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"), {}
        )
        media.width = video_stream.get("width") or media.width
        media.height = video_stream.get("height") or media.height
        with contextlib.suppress(TypeError, ValueError):
            media.duration = float(info.get("format", {}).get("duration"))

        poster = tempfile.NamedTemporaryFile(suffix=".webp", delete=False)  # noqa: SIM115
        poster.close()
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-ss",
                "1",
                "-i",
                path,
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-1",
                poster.name,
            ],
            capture_output=True,
            timeout=120,
        )
        try:
            if os.path.getsize(poster.name) > 0:
                with open(poster.name, "rb") as fh:
                    media.thumbnail.save("poster.webp", ContentFile(fh.read()), save=False)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(poster.name)


def _process_audio(media: MediaFile) -> None:
    if not ffmpeg_available():
        return
    with _local_copy(media) as path:
        info = _ffprobe(path)
        with contextlib.suppress(TypeError, ValueError):
            media.duration = float(info.get("format", {}).get("duration"))
        if media.kind == MediaKind.VOICE:
            media.waveform = _waveform(path)


def _waveform(path: str, buckets: int = WAVEFORM_BUCKETS) -> list[float]:
    """Decode to mono 16-bit PCM and reduce to `buckets` normalized peaks (0..1)."""
    result = subprocess.run(
        [FFMPEG, "-v", "quiet", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True,
        timeout=120,
    )
    raw = result.stdout
    if not raw:
        return []
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    if not samples:
        return []
    step = max(1, len(samples) // buckets)
    peaks = []
    for i in range(0, len(samples), step):
        window = samples[i : i + step]
        peak = max((abs(s) for s in window), default=0) / 32768.0
        peaks.append(round(peak, 3))
    return peaks[:buckets]
