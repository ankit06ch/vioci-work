"""Assess raster schematic quality and enhance low-quality uploads for parse/VLM."""

from __future__ import annotations

import io

import numpy as np


def assess_quality(png_bytes: bytes) -> float:
    """0–1 score; lower means blurrier / lower resolution."""
    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp = min(1.0, lap_var / 500.0)
    res = min(1.0, min(h, w) / 1200.0)
    return round(0.55 * sharp + 0.45 * res, 3)


def _min_dimension(png_bytes: bytes) -> int:
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        w, h = img.size
    return min(w, h)


def needs_enhancement(score: float, png_bytes: bytes) -> bool:
    """Only enhance genuinely low-res / blurry uploads — not clean white-background schematics."""
    if score >= 0.38:
        return False
    if _min_dimension(png_bytes) >= 900:
        return False
    return score < 0.32


def enhance_image(png_bytes: bytes, *, max_dim_px: int = 2400) -> bytes:
    """Alias for gentle enhance (legacy destructive grayscale path removed)."""
    return enhance_image_gentle(png_bytes, max_dim_px=max_dim_px)


def enhance_image_gentle(png_bytes: bytes, *, max_dim_px: int = 2400) -> bytes:
    """Mild RGB upscale + unsharp mask — preserves colors and line art (no grayscale wash)."""
    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    if max(h, w) < max_dim_px * 0.75:
        scale = min(2.0, (max_dim_px * 0.85) / float(max(h, w)))
        rgb = cv2.resize(
            rgb,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    blur = cv2.GaussianBlur(rgb, (0, 0), 1.0)
    rgb = cv2.addWeighted(rgb, 1.12, blur, -0.12, 0)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _estimate_font_size(text: str, box_h: float, box_w: float) -> int:
    n = max(len(text), 1)
    by_h = int(box_h * 0.72)
    by_w = int(box_w / max(n * 0.55, 1))
    return max(10, min(48, by_h, by_w))


def enhance_image_text_regions(png_bytes: bytes) -> tuple[bytes, int]:
    """Deprecated destructive OCR overlay — not used in product paths."""
    return enhance_image_gentle(png_bytes), 0


def assess_and_maybe_enhance(png_bytes: bytes) -> tuple[bytes, float, bool]:
    score = assess_quality(png_bytes)
    if not needs_enhancement(score, png_bytes):
        return png_bytes, score, False
    return enhance_image_gentle(png_bytes), score, True
