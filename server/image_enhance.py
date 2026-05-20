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


def needs_enhancement(score: float) -> bool:
    return score < 0.42


def enhance_image(png_bytes: bytes, *, max_dim_px: int = 2400) -> bytes:
    """Upscale, denoise, and sharpen a low-quality schematic raster."""
    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = 1.0
    if max(h, w) < max_dim_px * 0.75:
        scale = min(2.5, (max_dim_px * 0.85) / float(max(h, w)))
        rgb = cv2.resize(
            rgb,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    den = cv2.bilateralFilter(gray, d=7, sigmaColor=60, sigmaSpace=60)
    sharp = cv2.addWeighted(den, 1.35, cv2.GaussianBlur(den, (0, 0), 1.2), -0.35, 0)
    rgb = cv2.cvtColor(sharp, cv2.COLOR_GRAY2RGB)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _estimate_font_size(text: str, box_h: float, box_w: float) -> int:
    n = max(len(text), 1)
    by_h = int(box_h * 0.72)
    by_w = int(box_w / max(n * 0.55, 1))
    return max(10, min(48, by_h, by_w))


def enhance_image_text_regions(png_bytes: bytes) -> tuple[bytes, int]:
    """Re-draw detected text regions with crisp replacement labels (OCR → clear overlay)."""
    import io

    import cv2
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    pil = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    spans: list[tuple[str, int, int, int, int]] = []
    try:
        from schemagraph.cv.ocr import detect_text_spans

        for t in detect_text_spans(gray):
            if not t.text or len(t.text.strip()) < 1:
                continue
            bb = t.bbox
            spans.append(
                (
                    t.text.strip(),
                    int(bb.x),
                    int(bb.y),
                    int(bb.w),
                    int(bb.h),
                )
            )
    except Exception:
        pass

    if not spans:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        n, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        for i in range(1, min(n, 80)):
            x, y, bw, bh, area = stats[i]
            if area < 60 or bw < 6 or bh < 5:
                continue
            spans.append((f"", int(x), int(y), int(bw), int(bh)))

    font_paths = [
        "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    count = 0
    for text, x, y, bw, bh in spans:
        pad = max(2, int(min(bw, bh) * 0.08))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + bw + pad)
        y1 = min(h, y + bh + pad)
        region = rgb[y0:y1, x0:x1]
        if region.size == 0:
            continue
        bg = int(np.median(region.reshape(-1, 3), axis=0).mean())
        bg = min(255, max(200, bg + 25))
        draw.rectangle([x0, y0, x1, y1], fill=(bg, bg, bg))
        if text:
            size = _estimate_font_size(text, y1 - y0, x1 - x0)
            font = ImageFont.load_default()
            for fp in font_paths:
                try:
                    font = ImageFont.truetype(fp, size)
                    break
                except Exception:
                    continue
            draw.text((x0 + pad, y0 + pad), text, fill=(12, 12, 16), font=font)
        count += 1

    if count == 0:
        return enhance_image(png_bytes), 0

    return enhance_image(_pil_png(pil)), count


def _pil_png(pil: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    pil.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def enhance_image_full(png_bytes: bytes, *, max_dim_px: int = 2400) -> tuple[bytes, int]:
    """Text-aware enhance, then global sharpen/upscale."""
    text_bytes, n = enhance_image_text_regions(png_bytes)
    return enhance_image(text_bytes, max_dim_px=max_dim_px), n


def assess_and_maybe_enhance(png_bytes: bytes) -> tuple[bytes, float, bool]:
    score = assess_quality(png_bytes)
    if needs_enhancement(score):
        enhanced, _ = enhance_image_full(png_bytes)
        return enhanced, score, True
    return png_bytes, score, False
