"""
Image processing helpers (Pillow).

Validates uploaded images and produces normalised, size-bounded versions for
avatars/covers. Heavy media work (video transcode, multi-size thumbnails) is
handled asynchronously in the media phase; this is the lightweight, synchronous
path for profile images.
"""

from __future__ import annotations

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Conservative ceiling on decoded pixels to mitigate decompression-bomb attacks.
Image.MAX_IMAGE_PIXELS = 64_000_000  # ~64 MP

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


def process_image(
    uploaded_file,
    *,
    max_size: tuple[int, int],
    output_format: str = "WEBP",
    quality: int = 85,
) -> ContentFile:
    """Validate, EXIF-orient, downscale-to-fit, and re-encode an uploaded image.

    Returns a ContentFile ready to assign to an ImageField. Raises ValidationError
    on anything that isn't a supported, decodable image.
    """
    try:
        image = Image.open(uploaded_file)
        image.verify()  # cheap integrity check; consumes the file object
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Uploaded file is not a valid image.") from exc

    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(
            f"Unsupported image format. Allowed: {', '.join(sorted(ALLOWED_FORMATS))}."
        )

    # verify() leaves the image unusable; reopen for the actual transform.
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)  # honour camera orientation

    if output_format in {"JPEG", "WEBP"} and image.mode in {"RGBA", "P", "LA"}:
        image = image.convert("RGB")

    image.thumbnail(max_size, Image.LANCZOS)  # in-place, preserves aspect ratio

    buffer = io.BytesIO()
    save_kwargs = {"format": output_format}
    if output_format in {"JPEG", "WEBP"}:
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    image.save(buffer, **save_kwargs)
    buffer.seek(0)

    extension = "webp" if output_format == "WEBP" else output_format.lower()
    return ContentFile(buffer.read(), name=f"image.{extension}")
