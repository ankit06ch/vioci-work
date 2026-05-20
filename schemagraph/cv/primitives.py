"""Classical CV primitive extraction.

Produces a :class:`PrimitiveLayer` with detected lines, rectangles, circles,
arrows, and junction dots. The output feeds both the VLM (as structural
hints) and the IR builder (for pixel reconciliation).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from schemagraph.config import get_settings
from schemagraph.ingest.normalize import NormalizedRaster, normalize_raster
from schemagraph.ir import ids as _ids
from schemagraph.ir.schema import BBox, PrimitiveLayer, PrimitiveShape


def detect_primitives(
    png_bytes: bytes,
    *,
    diagram_id: str = "anon",
    normalized: Optional[NormalizedRaster] = None,
) -> PrimitiveLayer:
    """Detect low-level shape primitives from a raster image."""

    import cv2

    settings = get_settings()
    if normalized is None:
        normalized = normalize_raster(png_bytes, max_dim_px=settings.cv_max_image_dim_px)

    binary = normalized.binary
    gray = normalized.gray
    h, w = gray.shape[:2]

    shapes: list[PrimitiveShape] = []

    # --- lines via probabilistic Hough --------------------------------
    edges = cv2.Canny(gray, settings.cv_canny_low, settings.cv_canny_high)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360,
        threshold=settings.cv_hough_threshold,
        minLineLength=settings.cv_hough_min_line_length,
        maxLineGap=settings.cv_hough_max_line_gap,
    )
    if lines is not None:
        for ln in lines:
            x1, y1, x2, y2 = (float(v) for v in ln[0])
            pts = [(x1, y1), (x2, y2)]
            pid = _ids.primitive_id(diagram_id, "line", pts)
            shapes.append(
                PrimitiveShape(
                    id=pid,
                    kind="line",
                    points=pts,
                    bbox=BBox(
                        x=min(x1, x2),
                        y=min(y1, y2),
                        w=abs(x2 - x1),
                        h=abs(y2 - y1),
                    ),
                    score=1.0,
                )
            )

    # --- closed contours -> rects / polygons --------------------------
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < settings.cv_min_component_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw < 8 or ch < 8 or cw > w * 0.95 or ch > h * 0.95:
            continue
        kind: str
        pts: list[tuple[float, float]] | None = None
        if len(approx) == 4:
            kind = "rect"
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
        elif len(approx) >= 6:
            # try circle/ellipse fit
            (cx, cy), radius = cv2.minEnclosingCircle(cnt)
            circle_area = np.pi * radius * radius
            if circle_area > 0 and area / circle_area > 0.7:
                kind = "circle"
            else:
                kind = "polyline"
                pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
        else:
            continue
        pid = _ids.primitive_id(diagram_id, kind, (x, y, cw, ch))
        shapes.append(
            PrimitiveShape(
                id=pid,
                kind=kind,  # type: ignore[arg-type]
                points=pts,
                bbox=BBox(x=float(x), y=float(y), w=float(cw), h=float(ch)),
                score=float(min(1.0, area / (w * h * 0.5))),
                attrs={"area": float(area)},
            )
        )

    # --- junction dots: small filled circles --------------------------
    # (cheap heuristic; refined in later phases)
    # use HoughCircles on inverted gray
    circles = cv2.HoughCircles(
        cv2.GaussianBlur(gray, (5, 5), 0),
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=10,
        param1=120,
        param2=18,
        minRadius=2,
        maxRadius=8,
    )
    if circles is not None:
        for c in circles[0]:
            cx, cy, r = (float(v) for v in c)
            pid = _ids.primitive_id(diagram_id, "junction", (cx, cy, r))
            shapes.append(
                PrimitiveShape(
                    id=pid,
                    kind="junction",
                    points=[(cx, cy)],
                    bbox=BBox(x=cx - r, y=cy - r, w=2 * r, h=2 * r),
                    score=0.6,
                    attrs={"radius": r},
                )
            )

    return PrimitiveLayer(width_px=int(w), height_px=int(h), shapes=shapes)
