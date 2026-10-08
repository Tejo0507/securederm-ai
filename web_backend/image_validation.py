"""Shared image-upload safety checks — used by both dataset upload and
predict, so both endpoints reject the same spoofed-content-type / bogus
file attacks the same way instead of drifting apart over time."""

import io
import warnings

from PIL import Image, UnidentifiedImageError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB per image
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "TIFF", "WEBP"}

# A tiny, highly compressed PNG can declare billions of pixels and exhaust
# memory when decoded (a "decompression bomb"); the byte-size cap above
# doesn't help. Wound photos never need more than this.
MAX_IMAGE_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp", "TIFF": ".tif", "WEBP": ".webp"}


def sanitize_image(content: bytes) -> tuple[bytes, str]:
    """Re-encode a validated image from raw pixels only; return (bytes, extension).

    Clinical photos routinely carry EXIF (GPS position, device and owner
    names, timestamps), PNG text chunks and TIFF tags — identifying data
    that must never reach disk or a training set. Rebuilding the image from
    its pixel buffer drops every metadata block, ICC profile and thumbnail.
    Call only on content already accepted by is_genuine_image().
    """
    with Image.open(io.BytesIO(content)) as img:
        fmt = img.format
        mode = img.mode if img.mode in ("L", "RGB") else "RGB"
        pixels = img.convert(mode)
        clean = Image.frombytes(mode, pixels.size, pixels.tobytes())

    out = io.BytesIO()
    if fmt == "JPEG":
        clean.save(out, format="JPEG", quality=95)
    else:
        clean.save(out, format=fmt)
    return out.getvalue(), _EXTENSIONS[fmt]


def is_genuine_image(content: bytes) -> bool:
    """Verify file content is really a decodable image, not just a spoofed
    Content-Type header on arbitrary bytes — and not an oversized one."""
    try:
        # Pillow only *warns* between 1x and 2x the pixel limit; treat that
        # as a rejection too instead of letting the image through.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as img:
                if img.width * img.height > MAX_IMAGE_PIXELS:
                    return False
                img.verify()
            # verify() can leave the parser in a state that can't decode
            # pixel data afterwards, so re-open for a real format check.
            with Image.open(io.BytesIO(content)) as img:
                return img.format in ALLOWED_IMAGE_FORMATS
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        ValueError,
        SyntaxError,
    ):
        return False
