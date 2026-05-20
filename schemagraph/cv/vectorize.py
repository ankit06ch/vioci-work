"""Raster -> vector geometry.

Produces a :class:`VectorLayer` by contour-tracing the binary image, plus
straight-line approximation. Useful as a fallback when the input is purely
raster (no native SVG to preserve).
"""

from __future__ import annotations

import numpy as np

from schemagraph.ir.schema import VectorLayer, VectorPath


def vectorize_binary(binary: np.ndarray, simplify_eps: float = 1.5) -> VectorLayer:
    import cv2

    h, w = binary.shape[:2]
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    paths: list[VectorPath] = []
    for cnt in contours:
        if cv2.arcLength(cnt, False) < 8:
            continue
        approx = cv2.approxPolyDP(cnt, simplify_eps, False)
        pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
        if len(pts) < 2:
            continue
        kind = "polygon" if np.array_equal(approx[0], approx[-1]) else "polyline"
        paths.append(VectorPath(kind=kind, points=pts, closed=(kind == "polygon")))
    return VectorLayer(
        width_px=float(w), height_px=float(h), paths=paths, source="raster_vectorized"
    )
