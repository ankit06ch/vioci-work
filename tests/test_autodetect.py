"""Tests for autodetection heuristics."""

from __future__ import annotations

from pathlib import Path

from schemagraph.autodetect import infer_annotation_domain, infer_handdrawn
from schemagraph.ir.schema import Diagram, Node, Provenance, SourceMeta

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _prov() -> Provenance:
    return Provenance(stage="vlm", producer="test")


def _src() -> SourceMeta:
    return SourceMeta(
        uri="test.png",
        sha256="0" * 64,
        mime="image/png",
        width_px=100,
        height_px=100,
    )


def test_infer_annotation_domain_electrical():
    d = Diagram(
        id="d1",
        source=_src(),
        nodes=[
            Node(
                id="n1",
                kind="resistor",
                label="R1",
                provenance=_prov(),
            ),
        ],
        domain="electrical",
    )
    assert infer_annotation_domain(d) == "electrical"


def test_infer_annotation_domain_generic_when_empty():
    d = Diagram(
        id="d2",
        source=_src(),
        nodes=[
            Node(
                id="n1",
                kind="opaque_widget",
                label="quxorph_node",
                provenance=_prov(),
            ),
        ],
    )
    assert infer_annotation_domain(d) == "generic"


def test_infer_handdrawn_on_files():
    clean = REPO / "examples" / "electrical_rc_circuit.png"
    sketch = REPO / "examples" / "handdrawn_rc_circuit.png"
    if clean.exists():
        assert infer_handdrawn(clean) is False
    if sketch.exists():
        assert infer_handdrawn(sketch) is True
