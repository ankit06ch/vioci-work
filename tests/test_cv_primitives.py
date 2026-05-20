"""CV primitive extraction smoke test."""

from __future__ import annotations

from schemagraph.cv.primitives import detect_primitives


def test_detect_rectangles_and_lines(small_rc_circuit_png):
    layer = detect_primitives(small_rc_circuit_png, diagram_id="t")
    kinds = [s.kind for s in layer.shapes]
    assert "rect" in kinds
    assert "line" in kinds
    rects = [s for s in layer.shapes if s.kind == "rect"]
    assert len(rects) >= 2
