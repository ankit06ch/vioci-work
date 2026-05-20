"""Leader-line part detection places bboxes on satellite body, not whole image."""

from __future__ import annotations

import json
from pathlib import Path

from server.annotation_detect import auto_detect_annotations

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "workspace" / "a4b500d8-2322-46d6-a2fb-57912a6e84e1"


def test_leader_lines_create_per_component_bboxes():
    if not PROJECT.exists():
        return
    png = (PROJECT / "source.png").read_bytes()
    diagram = json.loads((PROJECT / "diagram.annotated.json").read_text(encoding="utf-8"))
    parts = auto_detect_annotations(png, diagram, existing=None)
    with_bbox = [p for p in parts if p.bbox]
    assert len(with_bbox) >= 6, f"expected multiple part boxes, got {len(with_bbox)}"
    w, h = diagram["source"]["width_px"], diagram["source"]["height_px"]
    huge = [p for p in with_bbox if p.bbox and p.bbox.w * p.bbox.h > 0.25 * w * h]
    assert not huge, "should not keep whole-satellite bbox"
    solar = next((p for p in parts if "solar" in p.name.lower()), None)
    assert solar and solar.bbox, "Solar Paddle should have a body bbox"
    assert solar.vectors, "should include leader line vectors"
    line_vecs = [v for v in solar.vectors if v.kind in ("line", "polyline")]
    assert line_vecs, "leader line should be drawn"
    poly_vecs = [v for v in solar.vectors if v.kind == "polygon"]
    assert poly_vecs, "component should use shape polygon not only square"
    assert len(poly_vecs[0].points) >= 3
