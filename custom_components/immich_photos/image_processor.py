"""Image processing utilities for Immich Photos integration."""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .const import (
    COMBINED_IMAGE_WIDTH,
    COMBINED_IMAGE_HEIGHT,
    SINGLE_IMAGE_WIDTH,
    SINGLE_IMAGE_HEIGHT,
)

if TYPE_CHECKING:
    from .api import ImmichAsset

_LOGGER = logging.getLogger(__name__)

OUTPUT_SIZE_COMBINED = (SINGLE_IMAGE_WIDTH, COMBINED_IMAGE_HEIGHT)
OUTPUT_SIZE_SINGLE = (SINGLE_IMAGE_WIDTH, SINGLE_IMAGE_HEIGHT)
JPEG_QUALITY = 85


def process_image(
    primary_bytes: bytes,
    secondary_bytes: bytes | None,
    crop_mode: str,
    primary_asset: "ImmichAsset | None" = None,
    secondary_asset: "ImmichAsset | None" = None,
) -> bytes:
    """Process and optionally combine images. Returns JPEG bytes."""
    if not PIL_AVAILABLE:
        _LOGGER.warning("Pillow not available, returning raw image bytes")
        return primary_bytes

    primary_img = Image.open(io.BytesIO(primary_bytes)).convert("RGB")
    primary_img = ImageOps.exif_transpose(primary_img)

    if crop_mode == "Original":
        return _resize_original(primary_img)

    if crop_mode == "Crop":
        return _crop_fit(primary_img, OUTPUT_SIZE_SINGLE)

    # Combine images mode
    if secondary_bytes is not None:
        try:
            secondary_img = Image.open(io.BytesIO(secondary_bytes)).convert("RGB")
            secondary_img = ImageOps.exif_transpose(secondary_img)
            return _combine_vertical(primary_img, secondary_img)
        except Exception as err:
            _LOGGER.warning("Failed to combine images, falling back to single: %s", err)

    # Fallback: single image crop
    return _crop_fit(primary_img, OUTPUT_SIZE_SINGLE)


def _resize_original(img: "Image.Image") -> bytes:
    """Resize preserving aspect ratio to fit within single output size."""
    img.thumbnail(OUTPUT_SIZE_SINGLE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def _crop_fit(img: "Image.Image", target: tuple[int, int]) -> bytes:
    """Center-crop image to fill the target size exactly."""
    img = ImageOps.fit(img, target, method=Image.LANCZOS, centering=(0.5, 0.5))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def _combine_vertical(
    top: "Image.Image",
    bottom: "Image.Image",
) -> bytes:
    """Stack two portrait images vertically into a single portrait canvas."""
    w, h = OUTPUT_SIZE_COMBINED
    half_h = h // 2

    top_fitted = ImageOps.fit(top, (w, half_h), method=Image.LANCZOS, centering=(0.5, 0.5))
    bottom_fitted = ImageOps.fit(bottom, (w, half_h), method=Image.LANCZOS, centering=(0.5, 0.5))

    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(top_fitted, (0, 0))
    canvas.paste(bottom_fitted, (0, half_h))

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()
