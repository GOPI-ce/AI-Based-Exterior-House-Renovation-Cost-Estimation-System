"""Decoding and normalising uploaded photos."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 60_000_000  # guard against decompression bombs

ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageRejected(ValueError):
    """The upload is not an image we can work with; the message is user-facing."""


@dataclass
class PreparedImage:
    jpeg: bytes
    width: int
    height: int
    rgb: np.ndarray  # H x W x 3, uint8


def prepare_upload(raw: bytes, max_side: int) -> PreparedImage:
    """Validate, auto-rotate (EXIF), downscale and re-encode an upload as JPEG."""
    try:
        image = Image.open(io.BytesIO(raw))
        fmt = image.format
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageRejected("This file could not be read as a photo. Please upload a JPG, PNG or WebP image.") from exc

    if fmt not in ACCEPTED_FORMATS:
        raise ImageRejected(f"{fmt or 'This'} images are not supported. Please upload a JPG, PNG or WebP photo.")

    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return PreparedImage(buffer.getvalue(), image.width, image.height, np.asarray(image))


def decode_jpeg(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
