"""AI-assisted part detection: diagram IR + OCR text regions → annotation overlays."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from server.annotation_schemas import AnnotationVector, BBoxPx, PartAnnotation
from server.annotation_service import _auto_vectors_for_bbox, _bbox_from_node, _node_display_name, seed_from_diagram


def _expand_bbox(bb: BBoxPx, pad: float, max_w: float, max_h: float) -> BBoxPx:
    x = max(0.0, bb.x - pad)
    y = max(0.0, bb.y - pad)
    w = min(max_w - x, bb.w + 2 * pad)
    h = min(max_h - y, bb.h + 2 * pad)
    return BBoxPx(x=x, y=y, w=max(12.0, w), h=max(10.0, h))


def _iou(a: BBoxPx, b: BBoxPx) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def _ocr_spans_from_image(png_bytes: bytes) -> list[tuple[str, BBoxPx, float]]:
    import io

    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape[:2]

    spans: list[tuple[str, BBoxPx, float]] = []
    try:
        from schemagraph.cv.ocr import detect_text_spans

        for t in detect_text_spans(gray):
            if not t.text or len(t.text.strip()) < 2:
                continue
            if t.confidence < 0.35:
                continue
            bb = t.bbox
            spans.append(
                (
                    t.text.strip(),
                    BBoxPx(x=float(bb.x), y=float(bb.y), w=float(bb.w), h=float(bb.h)),
                    float(t.confidence),
                )
            )
    except Exception:
        pass

    if spans:
        return spans

    # OpenCV fallback: connected components on inverted threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 80 or bw < 8 or bh < 6:
            continue
        if bw > w * 0.6 and bh > h * 0.3:
            continue
        aspect = bw / max(bh, 1)
        if aspect > 25 or aspect < 0.08:
            continue
        spans.append((f"region-{i}", BBoxPx(x=float(x), y=float(y), w=float(bw), h=float(bh)), 0.55))
    return spans


def _merge_ocr_parts(
    ocr_spans: list[tuple[str, BBoxPx, float]],
    existing: list[PartAnnotation],
    img_w: float,
    img_h: float,
) -> list[PartAnnotation]:
    out = list(existing)
    used_boxes = [a.bbox for a in out if a.bbox]

    for text, bb, conf in ocr_spans:
        expanded = _expand_bbox(bb, pad=max(4.0, bb.h * 0.15), max_w=img_w, max_h=img_h)
        if any(_iou(expanded, u) > 0.45 for u in used_boxes if u):
            continue
        name = text if not text.startswith("region-") else "Label"
        part = PartAnnotation(
            id=str(uuid.uuid4()),
            node_id=None,
            name=name,
            auto_detected=True,
            bbox=expanded,
            vectors=_auto_vectors_for_bbox(expanded, name),
            extra={"ocr_confidence": conf, "source": "ocr"},
        )
        out.append(part)
        used_boxes.append(expanded)
    return out


def auto_detect_annotations(
    png_bytes: bytes,
    diagram: dict[str, Any] | None,
    existing: list[PartAnnotation] | None = None,
) -> list[PartAnnotation]:
    """Fuse VLM diagram nodes with OCR label regions for automatic overlays."""
    import io

    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        w, h = img.size

    base = seed_from_diagram(diagram or {"nodes": []}, existing)
    ocr = _ocr_spans_from_image(png_bytes)
    return _merge_ocr_parts(ocr, base, float(w), float(h))
