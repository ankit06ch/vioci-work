"""Preprocessing tuned for hand-drawn schematics.

Hand-drawn input typically has:

* uneven lighting (photo of paper / whiteboard),
* paper grain and shadows,
* perspective skew (camera not perfectly perpendicular),
* wobbly strokes of varying thickness.

This module provides:

* :func:`prepare_handdrawn` — produces a normalized grayscale + clean
  binary image suitable for the existing :func:`detect_primitives`,
  using adaptive thresholding, morphological cleanup, and optional
  perspective correction.
* :func:`thin_strokes` — Zhang-Suen-like skeletonization, useful for
  refining wobbly hand-drawn lines before Hough detection.
* :func:`detect_paper_quad` — find the dominant quadrilateral (e.g. the
  paper boundary) so we can warp it back to a rectangle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class HandDrawnPrep:
    rgb: np.ndarray
    gray: np.ndarray
    binary: np.ndarray  # foreground = 255 (ink)
    skeleton: Optional[np.ndarray] = None
    warp_matrix: Optional[np.ndarray] = None


def prepare_handdrawn(
    png_bytes: bytes,
    *,
    correct_perspective: bool = True,
    skeletonize: bool = False,
    max_dim_px: int = 2048,
) -> HandDrawnPrep:
    """Hand-drawn-friendly preprocessing pipeline."""

    import cv2
    from PIL import Image
    import io as _io

    with Image.open(_io.BytesIO(png_bytes)) as im:
        rgb = np.array(im.convert("RGB"))

    h, w = rgb.shape[:2]
    if max(h, w) > max_dim_px:
        scale = max_dim_px / float(max(h, w))
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # remove paper shadow / illumination
    bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, np.ones((25, 25), np.uint8))
    diff = 255 - cv2.absdiff(gray, bg)
    norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # adaptive threshold (foreground = ink = 255)
    binary = cv2.adaptiveThreshold(
        norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 12
    )
    # clean tiny specks
    binary = cv2.medianBlur(binary, 3)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    warp_matrix = None
    if correct_perspective:
        quad = detect_paper_quad(binary)
        if quad is not None:
            rgb, binary, warp_matrix = _warp_to_rect(rgb, binary, quad)
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    skel = thin_strokes(binary) if skeletonize else None

    return HandDrawnPrep(
        rgb=rgb,
        gray=gray,
        binary=binary,
        skeleton=skel,
        warp_matrix=warp_matrix,
    )


def detect_paper_quad(binary: np.ndarray) -> Optional[np.ndarray]:
    """Return the 4 corner points of the dominant quadrilateral, or None."""
    import cv2

    h, w = binary.shape[:2]
    # invert: we want the paper boundary, not the ink
    contours, _ = cv2.findContours(255 - binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for cnt in contours[:3]:
        area = cv2.contourArea(cnt)
        if area < 0.4 * h * w:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            return _order_quad(pts)
    return None


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """TL, TR, BR, BL ordering."""
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    return np.array(
        [
            pts[np.argmin(s)],   # top-left
            pts[np.argmin(diff)],  # top-right
            pts[np.argmax(s)],   # bottom-right
            pts[np.argmax(diff)],  # bottom-left
        ],
        dtype=np.float32,
    )


def _warp_to_rect(rgb: np.ndarray, binary: np.ndarray, quad: np.ndarray):
    import cv2

    tl, tr, br, bl = quad
    wA = np.linalg.norm(br - bl)
    wB = np.linalg.norm(tr - tl)
    hA = np.linalg.norm(tr - br)
    hB = np.linalg.norm(tl - bl)
    W = int(max(wA, wB))
    H = int(max(hA, hB))
    if W < 64 or H < 64:
        return rgb, binary, None
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    rgb_w = cv2.warpPerspective(rgb, M, (W, H))
    bin_w = cv2.warpPerspective(binary, M, (W, H), flags=cv2.INTER_NEAREST)
    return rgb_w, bin_w, M


def thin_strokes(binary: np.ndarray) -> np.ndarray:
    """Zhang-Suen skeletonization via OpenCV-ximgproc when available, else a
    pure-NumPy fallback.

    Used to give the line detector a cleaner, thinner trace for wobbly
    hand-drawn strokes.
    """
    try:  # pragma: no cover - optional dependency
        import cv2.ximgproc as ximgproc  # type: ignore

        return ximgproc.thinning(binary)
    except Exception:
        return _skeletonize_numpy(binary)


def _skeletonize_numpy(binary: np.ndarray) -> np.ndarray:
    """Lightweight iterative erosion-skeletonization fallback."""
    import cv2

    img = (binary > 0).astype(np.uint8) * 255
    skel = np.zeros(img.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while True:
        eroded = cv2.erode(img, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(img, temp)
        skel = cv2.bitwise_or(skel, temp)
        img = eroded.copy()
        if cv2.countNonZero(img) == 0:
            break
    return skel
