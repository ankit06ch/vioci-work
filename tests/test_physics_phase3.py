"""Phase 3 tests: sympy equation parsing, variable binding, auto-constraints,
parametric overrides, and sweeps."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemagraph.api import annotate as api_annotate
from schemagraph.api import parse as api_parse
from schemagraph.ir.schema import (
    Diagram,
    Edge,
    Equation,
    Node,
    Parameter,
    Provenance,
    Quantity,
    SourceMeta,
)
from schemagraph.physics.equations import parse_equation, resolve_variables
from schemagraph.physics.parametric import apply_parameters, sweep
from schemagraph.registry import provider_registry
from schemagraph.vlm.fake_provider import FakeProvider


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


# ---------------------------------------------------------------------------
# Equation parsing
# ---------------------------------------------------------------------------


def test_parse_simple_equation():
    sympy_repr, syms, lhs, rhs = parse_equation("tau = R*C")
    assert sympy_repr is not None
    assert set(syms) == {"C", "R", "tau"}
    assert lhs == "tau"
    assert rhs == "R*C"


def test_parse_bare_expression():
    sympy_repr, syms, lhs, rhs = parse_equation("1 - exp(-t/tau)")
    assert sympy_repr is not None
    assert "t" in syms and "tau" in syms
    assert lhs is None
    assert rhs is not None


def test_parse_latex_equation():
    # LaTeX parsing requires antlr4 to be installed; skip cleanly if absent.
    pytest.importorskip("antlr4")
    sympy_repr, syms, lhs, rhs = parse_equation(r"V = I \cdot R")
    assert sympy_repr is not None
    assert set(syms) >= {"V", "I", "R"}


# ---------------------------------------------------------------------------
# Variable resolution
# ---------------------------------------------------------------------------


def _prov() -> Provenance:
    return Provenance(stage="user", producer="t")


def test_resolve_symbols_to_nodes_and_parameters():
    n = Node(id="n_R1", kind="resistor", label="R", provenance=_prov())
    c = Node(id="n_C1", kind="capacitor", label="C", provenance=_prov())
    tau_param = Parameter(id="p_tau", name="tau")
    bindings = resolve_variables(["R", "C", "tau"], nodes=[n, c], parameters=[tau_param])
    assert bindings["R"] == "n_R1.value"
    assert bindings["C"] == "n_C1.value"
    assert bindings["tau"] == "p_tau.value"


# ---------------------------------------------------------------------------
# Annotator wiring
# ---------------------------------------------------------------------------


RC_PAYLOAD = {
    "_producer": "fake:rc",
    "domain": "electrical",
    "nodes": [
        {"id": "Vs", "kind": "voltage_source", "label": "Vs", "anchor": [45, 125], "properties": {"value": "9V"}, "confidence": 0.95},
        {"id": "R1", "kind": "resistor", "label": "R", "anchor": [160, 120], "properties": {"value": "10kΩ"}, "confidence": 0.95},
        {"id": "C1", "kind": "capacitor", "label": "C", "anchor": [390, 120], "properties": {"value": "1uF"}, "confidence": 0.95},
        {"id": "GND", "kind": "ground", "label": "GND", "anchor": [265, 240], "confidence": 0.9},
    ],
    "edges": [
        {"source": "Vs", "target": "R1", "kind": "wire", "confidence": 0.9, "polyline": [[70, 120], [120, 120]]},
        {"source": "R1", "target": "C1", "kind": "wire", "confidence": 0.9, "polyline": [[200, 120], [380, 120]]},
        {"source": "C1", "target": "GND", "kind": "wire", "confidence": 0.85, "polyline": [[400, 120], [470, 120], [470, 230], [265, 230]]},
        {"source": "Vs", "target": "GND", "kind": "wire", "confidence": 0.85, "polyline": [[45, 150], [45, 230], [265, 230]]},
    ],
    "equations": [{"raw": "tau = R*C"}],
    "parameters": [
        {"name": "R", "default": {"value": 10000.0, "unit": "ohm"}, "targets": ["R1.value"]},
        {"name": "C", "default": {"value": 1e-6, "unit": "farad"}, "targets": ["C1.value"]},
    ],
}


@pytest.fixture
def rc_diagram():
    if not (EXAMPLES / "electrical_rc_circuit.png").exists():
        from examples.generate_fixtures import main as gen

        gen()

    def factory(**kwargs):
        return FakeProvider(payload=RC_PAYLOAD, **kwargs)

    provider_registry.register("fake-phase3", factory)
    return api_parse(EXAMPLES / "electrical_rc_circuit.png", provider="fake-phase3", domain="electrical")


def test_annotator_resolves_equation_variables(rc_diagram):
    annotated = api_annotate(rc_diagram, domain="electrical")
    assert annotated.equations
    eq = annotated.equations[0]
    assert eq.sympy_repr is not None
    # R and C should be bound. Resolution prefers parameters (the user-facing
    # knobs in this payload) over node labels; either binding is valid.
    assert set(eq.variables.keys()) >= {"R", "C"}
    r_param = next(p for p in annotated.parameters if p.name == "R")
    c_param = next(p for p in annotated.parameters if p.name == "C")
    assert eq.variables["R"] == f"{r_param.id}.value"
    assert eq.variables["C"] == f"{c_param.id}.value"


def test_annotator_resolves_equation_variables_to_nodes_when_no_param():
    """When no matching parameter exists, symbols bind to nodes by label."""
    diag = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[
            Node(id="n_R1", kind="resistor", label="R", provenance=_prov()),
            Node(id="n_C1", kind="capacitor", label="C", provenance=_prov()),
        ],
        equations=[Equation(id="eq1", raw="tau = R*C", provenance=_prov())],
    )
    annotated = api_annotate(diag, domain="electrical")
    eq = annotated.equations[0]
    assert eq.variables["R"] == "n_R1.value"
    assert eq.variables["C"] == "n_C1.value"


def test_annotator_auto_grounds_electrical(rc_diagram):
    annotated = api_annotate(rc_diagram, domain="electrical")
    # The ground node should generate a V=0 boundary condition.
    gnd_node = next(n for n in annotated.nodes if n.kind == "ground")
    bcs = [c for c in annotated.constraints if c.kind == "boundary_condition" and gnd_node.id in c.targets]
    assert bcs and "V = 0" in (bcs[0].expression or "")


# ---------------------------------------------------------------------------
# Parametric overrides
# ---------------------------------------------------------------------------


def test_apply_parameter_override(rc_diagram):
    annotated = api_annotate(rc_diagram, domain="electrical")
    # Param target should resolve relative to the actual resistor node id.
    r_node = next(n for n in annotated.nodes if n.kind == "resistor")
    annotated = annotated.model_copy(
        update={
            "parameters": [
                p.model_copy(update={"targets": [f"{r_node.id}.value"]})
                if p.name == "R"
                else p
                for p in annotated.parameters
            ]
        }
    )

    updated = apply_parameters(annotated, {"R": "22kohm"})
    r_updated = next(n for n in updated.nodes if n.kind == "resistor")
    val = r_updated.properties["value"]
    assert abs(val.value - 22000.0) < 1e-6
    assert "ohm" in val.unit


def test_apply_parameter_bounds_violation():
    diag = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[Node(id="r1", kind="resistor", label="R", provenance=_prov())],
        parameters=[
            Parameter(id="p", name="R", bounds=(1.0, 1000.0), targets=["r1.value"])
        ],
    )
    with pytest.raises(ValueError):
        apply_parameters(diag, {"R": 1e6})


def test_sweep_returns_cartesian_product():
    diag = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[Node(id="r1", kind="resistor", label="R", provenance=_prov())],
        parameters=[Parameter(id="p", name="R", targets=["r1.value"])],
    )
    results = sweep(diag, {"R": [100.0, 1000.0]})
    assert len(results) == 2
    values = [r["r1"].properties["value"].value for _, r in [(o, d.node_index()) for o, d in results]]
    assert sorted(values) == [100.0, 1000.0]
