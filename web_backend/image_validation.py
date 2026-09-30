"""Shared image-upload safety checks — used by both dataset upload and
predict, so both endpoints reject the same spoofed-content-type / bogus
file attacks the same way instead of drifting apart over time."""

import io

from PIL import Image, UnidentifiedImageError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB per image
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "TIFF", "WEBP"}


def is_genuine_image(content: bytes) -> bool:
    """Verify file content is really a decodable image, not just a spoofed
    Content-Type header on arbitrary bytes."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        # verify() can leave the parser in a state that can't decode
        # pixel data afterwards, so re-open for a real format check.
        with Image.open(io.BytesIO(content)) as img:
            return img.format in ALLOWED_IMAGE_FORMATS
    except (UnidentifiedImageError, OSError, ValueError):
        return False
