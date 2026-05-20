"""End-to-end tests against the example fixture set.

For each canonical input type (electrical schematic, truss, control block
diagram, plotted line graph), we run the full pipeline with a
deterministic fake VLM payload that mirrors what a real VLM would produce.
This verifies the Phase 1 vertical slice (ingest -> CV -> VLM -> IR ->
exports) on all four diagram families.
"""

from __future__ import annotations

import json
import math
import pickle
from pathlib import Path

import pytest

from schemagraph.api import annotate as api_annotate
from schemagraph.api import export as api_export
from schemagraph.api import parse as api_parse
from schemagraph.api import validate as api_validate
from schemagraph.registry import provider_registry
from schemagraph.vlm.fake_provider import FakeProvider


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _ensure_examples_present():
    if not EXAMPLES.exists() or not any(EXAMPLES.glob("*.png")):
        # generate on demand so tests are hermetic
        from examples.generate_fixtures import main as gen

        gen()


_ensure_examples_present()


def _register(name: str, payload: dict):
    def factory(**kwargs):
        return FakeProvider(payload=payload, **kwargs)

    provider_registry.register(name, factory)
    return name


# ---------------------------------------------------------------------------
# Fixture payloads (mirror each example image)
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
        {"source": "Vs", "target": "R1", "kind": "wire", "polyline": [[70, 120], [120, 120]], "confidence": 0.9},
        {"source": "R1", "target": "C1", "kind": "wire", "polyline": [[200, 120], [380, 120]], "confidence": 0.9},
        {"source": "C1", "target": "GND", "kind": "wire", "polyline": [[400, 120], [470, 120], [470, 230], [265, 230]], "confidence": 0.85},
        {"source": "Vs", "target": "GND", "kind": "wire", "polyline": [[45, 150], [45, 230], [265, 230]], "confidence": 0.85},
    ],
    "constraints": [
        {"kind": "boundary_condition", "targets": ["GND"], "expression": "V = 0"}
    ],
    "equations": [{"raw": "tau = R*C"}],
    "parameters": [
        {"name": "R", "default": {"value": 10000.0, "unit": "ohm"}, "targets": ["R1.value"]},
        {"name": "C", "default": {"value": 1e-6, "unit": "farad"}, "targets": ["C1.value"]},
    ],
}


TRUSS_PAYLOAD = {
    "_producer": "fake:truss",
    "domain": "mechanical",
    "nodes": [
        {"id": "A", "kind": "joint", "label": "A", "anchor": [60, 280], "confidence": 0.95},
        {"id": "B", "kind": "joint", "label": "B", "anchor": [180, 100], "confidence": 0.95},
        {"id": "C", "kind": "joint", "label": "C", "anchor": [300, 280], "confidence": 0.95},
        {"id": "D", "kind": "joint", "label": "D", "anchor": [420, 100], "confidence": 0.95},
        {"id": "E", "kind": "joint", "label": "E", "anchor": [540, 280], "confidence": 0.95},
        {"id": "P", "kind": "force", "label": "P", "anchor": [180, 70], "properties": {"value": "5kN"}, "confidence": 0.9},
    ],
    "edges": [
        {"source": "A", "target": "B", "kind": "rigid_link", "confidence": 0.9},
        {"source": "B", "target": "C", "kind": "rigid_link", "confidence": 0.9},
        {"source": "A", "target": "C", "kind": "rigid_link", "confidence": 0.9},
        {"source": "C", "target": "D", "kind": "rigid_link", "confidence": 0.9},
        {"source": "B", "target": "D", "kind": "rigid_link", "confidence": 0.9},
        {"source": "D", "target": "E", "kind": "rigid_link", "confidence": 0.9},
        {"source": "C", "target": "E", "kind": "rigid_link", "confidence": 0.9},
        {"source": "P", "target": "B", "kind": "load", "directed": True, "confidence": 0.9},
    ],
    "constraints": [
        {"kind": "fixed", "targets": ["A"]},
        {"kind": "roller", "targets": ["E"]},
    ],
}


BLOCK_PAYLOAD = {
    "_producer": "fake:block",
    "domain": "control",
    "nodes": [
        {"id": "IN", "kind": "block", "label": "Input", "anchor": [100, 120], "confidence": 0.95},
        {"id": "P", "kind": "block", "label": "Plant", "anchor": [295, 120], "confidence": 0.95},
        {"id": "S", "kind": "block", "label": "Sensor", "anchor": [495, 120], "confidence": 0.95},
    ],
    "edges": [
        {"source": "IN", "target": "P", "kind": "signal", "directed": True, "polyline": [[160, 120], [230, 120]], "confidence": 0.95},
        {"source": "P", "target": "S", "kind": "signal", "directed": True, "polyline": [[360, 120], [430, 120]], "confidence": 0.95},
        {"source": "S", "target": "IN", "kind": "signal", "label": "feedback", "directed": True, "polyline": [[560, 120], [590, 120], [590, 200], [40, 200], [40, 120]], "confidence": 0.9},
    ],
}


_PLOT_T = [i / 40.0 for i in range(0, 200)]
PLOT_PAYLOAD = {
    "_producer": "fake:plot",
    "domain": "graph",
    "nodes": [],
    "edges": [],
    "datasets": [
        {
            "name": "step_response",
            "axes": ["t (s)", "V"],
            "series": [
                {"name": "V(t)", "values": [1 - math.exp(-t) for t in _PLOT_T]},
            ],
        }
    ],
    "equations": [{"raw": "V(t) = 1 - exp(-t/tau)"}],
}


CASES = [
    ("electrical_rc_circuit.png", RC_PAYLOAD, "electrical", 4, 4),
    ("truss_diagram.png", TRUSS_PAYLOAD, "mechanical", 6, 8),
    ("block_diagram.png", BLOCK_PAYLOAD, "control", 3, 3),
    ("step_response_plot.png", PLOT_PAYLOAD, "graph", 0, 0),
]


@pytest.mark.parametrize("filename,payload,domain,n_nodes,n_edges", CASES)
def test_fixture_pipeline(tmp_path, filename, payload, domain, n_nodes, n_edges):
    provider_name = _register(f"fake-{filename}", payload)
    fixture = EXAMPLES / filename
    assert fixture.exists()

    diagram = api_parse(fixture, provider=provider_name, domain=domain)
    assert len(diagram.nodes) == n_nodes
    assert len(diagram.edges) == n_edges
    assert diagram.domain == domain

    report = api_validate(diagram)
    assert report.ok, [str(i) for i in report.issues]

    # Annotation only meaningful for non-plot inputs
    if n_nodes > 0:
        annotated = api_annotate(diagram, domain=domain)
    else:
        annotated = diagram

    # All three exporters succeed
    nx_path = tmp_path / "g.gpickle"
    api_export(annotated, format="networkx", path=nx_path)
    with open(nx_path, "rb") as fh:
        G = pickle.load(fh)
    assert G.number_of_nodes() == len(annotated.nodes)

    gml_path = tmp_path / "g.graphml"
    api_export(annotated, format="graphml", path=gml_path)
    assert "<graphml" in gml_path.read_text()

    ld_path = tmp_path / "g.jsonld"
    api_export(annotated, format="jsonld", path=ld_path)
    doc = json.loads(ld_path.read_text())
    assert doc["@type"] == "sg:Diagram"

    if "datasets" in payload and payload["datasets"]:
        assert len(annotated.datasets) == len(payload["datasets"])
        assert len(annotated.datasets[0].series[0].values) == len(_PLOT_T)


def test_rc_circuit_unit_resolution(tmp_path):
    provider_name = _register("fake-units", RC_PAYLOAD)
    diagram = api_parse(EXAMPLES / "electrical_rc_circuit.png", provider=provider_name, domain="electrical")
    annotated = api_annotate(diagram, domain="electrical")

    r = next(n for n in annotated.nodes if n.kind == "resistor")
    c = next(n for n in annotated.nodes if n.kind == "capacitor")
    rv = r.properties["value"]
    cv = c.properties["value"]
    assert abs(rv.value - 10000.0) < 1.0
    assert "ohm" in rv.unit
    assert abs(cv.value - 1e-6) < 1e-9
    assert "farad" in cv.unit
