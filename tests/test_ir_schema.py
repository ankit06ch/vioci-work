"""Tests for the IR pydantic schema and ID determinism."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemagraph.ir import ids
from schemagraph.ir.schema import (
    BBox,
    Constraint,
    Diagram,
    Edge,
    Equation,
    GeometryRef,
    Node,
    Port,
    Provenance,
    Quantity,
    SourceMeta,
)
from schemagraph.ir.validate import validate_diagram


def _prov() -> Provenance:
    return Provenance(stage="user", producer="test")


def _node(id_: str, kind: str = "resistor", anchor=(10.0, 10.0)) -> Node:
    return Node(
        id=id_,
        kind=kind,
        label="10k",
        properties={"value": Quantity(value=1.0, unit="ohm")},
        geometry=GeometryRef(bbox=BBox(x=0, y=0, w=20, h=20)),
        provenance=_prov(),
    )


def test_quantity_str_roundtrip():
    q = Quantity(value=10000.0, unit="ohm", raw="10k")
    assert "10000.0 ohm" in str(q)


def test_diagram_unique_node_ids():
    src = SourceMeta(width_px=100, height_px=100)
    with pytest.raises(ValidationError):
        Diagram(
            id="d",
            source=src,
            nodes=[_node("n1"), _node("n1")],
        )


def test_diagram_index_helpers():
    d = Diagram(
        id="d",
        source=SourceMeta(width_px=10, height_px=10),
        nodes=[_node("n1"), _node("n2", kind="capacitor", anchor=(50, 50))],
    )
    assert set(d.node_index().keys()) == {"n1", "n2"}


def test_validate_detects_dangling_edge():
    d = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[_node("n1")],
        edges=[
            Edge(id="e1", source="n1", target="ghost", provenance=_prov()),
        ],
    )
    report = validate_diagram(d)
    assert not report.ok
    assert any(i.code == "EDGE_DANGLING_ENDPOINT" for i in report.issues)


def test_validate_passes_clean_graph():
    n1 = _node("n1", anchor=(10, 10))
    n2 = _node("n2", kind="capacitor", anchor=(40, 10))
    e = Edge(id="e1", source="n1", target="n2", kind="wire", provenance=_prov())
    d = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[n1, n2],
        edges=[e],
    )
    report = validate_diagram(d)
    assert report.ok


def test_validate_port_node_mismatch():
    n1 = _node("n1")
    p = Port(id="p1", node_id="other", role="anode")
    n1 = n1.model_copy(update={"ports": [p]})
    d = Diagram(id="d", source=SourceMeta(), nodes=[n1])
    report = validate_diagram(d)
    assert any(i.code == "PORT_BAD_NODE_REF" for i in report.issues)


def test_validate_dangling_equation_variable():
    n1 = _node("n1")
    eq = Equation(
        id="eq1", raw="tau = R*C", variables={"R": "ghost.value"}, provenance=_prov()
    )
    d = Diagram(id="d", source=SourceMeta(), nodes=[n1], equations=[eq])
    report = validate_diagram(d)
    assert any(i.code == "EQUATION_DANGLING_VARIABLE" for i in report.issues)


def test_validate_constraint_dangling_target():
    n1 = _node("n1")
    c = Constraint(id="c1", kind="equal", targets=["ghost"], provenance=_prov())
    d = Diagram(id="d", source=SourceMeta(), nodes=[n1], constraints=[c])
    report = validate_diagram(d)
    assert any(i.code == "CONSTRAINT_DANGLING_TARGET" for i in report.issues)


def test_ids_are_deterministic_and_stable():
    a = ids.node_id("diag", "resistor", (10.0, 10.0), "10k")
    b = ids.node_id("diag", "resistor", (10.0, 10.0), "10k")
    c = ids.node_id("diag", "resistor", (10.0, 11.0), "10k")
    assert a == b
    assert a != c
    assert a.startswith("n_")


def test_ids_differ_across_kinds():
    assert ids.edge_id("d", "a", "b") != ids.edge_id("d", "b", "a")


def test_diagram_serialization_roundtrip():
    d = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[_node("n1"), _node("n2", kind="capacitor", anchor=(40, 10))],
        edges=[Edge(id="e1", source="n1", target="n2", kind="wire", provenance=_prov())],
    )
    s = d.model_dump_json()
    d2 = Diagram.model_validate_json(s)
    assert d2 == d
