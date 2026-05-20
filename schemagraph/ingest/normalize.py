"""Raster normalization: deskew, denoise, resize, color normalization.

Used before CV primitive extraction and before sending the image to a VLM.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class NormalizedRaster:
    gray: np.ndarray  # uint8 (H, W)
    rgb: np.ndarray  # uint8 (H, W, 3)
    binary: np.ndarray  # uint8 (H, W) - inverted (foreground=255)
    scale: float  # applied resize factor relative to original
    rotation_deg: float  # applied deskew rotation


def _decode_png(png_bytes: bytes) -> np.ndarray:
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        return np.array(img.convert("RGB"))


def normalize_raster(
    png_bytes: bytes,
    *,
    max_dim_px: int = 2048,
    deskew: bool = True,
    denoise: bool = True,
) -> NormalizedRaster:
    """Produce a normalized grayscale + binary representation suitable for CV."""

    import cv2

    rgb = _decode_png(png_bytes)
    h, w = rgb.shape[:2]
    scale = 1.0
    if max(h, w) > max_dim_px:
        scale = max_dim_px / float(max(h, w))
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if denoise:
        gray = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)

    rot_deg = 0.0
    if deskew:
        rot_deg = _estimate_skew_deg(gray)
        if abs(rot_deg) > 0.5:
            gray = _rotate(gray, rot_deg)
            rgb = _rotate(rgb, rot_deg)

    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )

    return NormalizedRaster(gray=gray, rgb=rgb, binary=binary, scale=scale, rotation_deg=rot_deg)


def _estimate_skew_deg(gray: np.ndarray) -> float:
    """Estimate dominant-line rotation via Hough transform on inverted edges."""
    import cv2

    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 360, threshold=200)
    if lines is None:
        return 0.0
    angles = []
    for rho_theta in lines[:50]:
        _, theta = rho_theta[0]
        deg = (theta * 180.0 / np.pi) - 90.0
        if -45.0 < deg < 45.0:
            angles.append(deg)
    if not angles:
        return 0.0
    return float(np.median(angles))


def _rotate(img: np.ndarray, deg: float) -> np.ndarray:
    import cv2

    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
