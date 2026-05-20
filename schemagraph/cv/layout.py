"""Region/panel segmentation.

Used to split multi-panel images (e.g. a sheet with several sub-diagrams)
into individually-parseable regions. Phase 0 implements a simple
connected-component-based panel finder; later phases can swap in
layout-aware models.
"""

from __future__ import annotations

import numpy as np

from schemagraph.ir.schema import BBox


def segment_panels(binary: np.ndarray, min_area_frac: float = 0.05) -> list[BBox]:
    """Return bounding boxes of large connected ink regions (likely panels)."""
    import cv2

    h, w = binary.shape[:2]
    total = float(h * w)
    num, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out: list[BBox] = []
    for i in range(1, num):
        x, y, cw, ch, area = stats[i]
        if area / total < min_area_frac:
            continue
        out.append(BBox(x=float(x), y=float(y), w=float(cw), h=float(ch)))
    if not out:
        out.append(BBox(x=0.0, y=0.0, w=float(w), h=float(h)))
    return out
