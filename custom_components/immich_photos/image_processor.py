"""Image processing utilities for Immich Photos integration.

Handles cropping, resizing, and combining two portrait images side-by-side
(inspired by ha-google-photos 'Combine images' mode).
"""
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

OUTPUT_SIZE_LANDSCAPE = (COMBINED_IMAGE_WIDTH, COMBINED_IMAGE_HEIGHT)
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

    if crop_mode == "Original":
        return _resize_original(primary_img)

    if crop_mode == "Crop":
        return _crop_fit(primary_img, OUTPUT_SIZE_SINGLE)

    # Combine images mode
    if secondary_bytes is not None:
        try:
            secondary_img = Image.open(io.BytesIO(secondary_bytes)).convert("RGB")
            return _combine_side_by_side(primary_img, secondary_img)
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


def _combine_side_by_side(
    left: "Image.Image",
    right: "Image.Image",
) -> bytes:
    """Combine two images side by side into a landscape canvas.

    Each image fills half the canvas height, cropped to fit.
    This mimics the 'Combine images' mode from ha-google-photos where two
    portrait images are placed next to each other in a landscape frame —
    resulting in less wasted pixels than cropping a single portrait to landscape.
    """
    w, h = OUTPUT_SIZE_LANDSCAPE
    half_w = w // 2

    # Fit each image into its half of the canvas
    left_fitted = ImageOps.fit(left, (half_w, h), method=Image.LANCZOS, centering=(0.5, 0.5))
    right_fitted = ImageOps.fit(right, (half_w, h), method=Image.LANCZOS, centering=(0.5, 0.5))

    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(left_fitted, (0, 0))
    canvas.paste(right_fitted, (half_w, 0))

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def should_combine(primary_asset: "ImmichAsset", canvas_aspect: float = 16 / 9) -> bool:
    """Determine if it makes sense to combine two images.

    Returns True if a single portrait image would lose more pixels
    to cropping than two portrait images side-by-side would.
    """
    if primary_asset is None:
        return False
    if primary_asset.width <= 0 or primary_asset.height <= 0:
        # Unknown dims — use is_portrait heuristic
        return primary_asset.is_portrait

    asset_ratio = primary_asset.width / primary_asset.height
    # If portrait, combining makes sense for a landscape canvas
    return asset_ratio < canvas_aspect / 2
