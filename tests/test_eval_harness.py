"""Tests for the golden-fixture eval harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemagraph.api import parse as api_parse
from schemagraph.eval.harness import (
    Metrics,
    diff_diagrams,
    evaluate_dataset,
)
from schemagraph.eval.report import render_html
from schemagraph.registry import provider_registry
from schemagraph.vlm.fake_provider import FakeProvider


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


# Use the same RC payload as the e2e fixture tests
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
}


@pytest.fixture
def dataset_dir(tmp_path: Path):
    """A two-fixture mini-dataset built from the existing example PNGs."""
    # ensure fixtures exist
    if not (EXAMPLES / "electrical_rc_circuit.png").exists():
        from examples.generate_fixtures import main as gen

        gen()

    def _register(name: str, payload):
        def factory(**kwargs):
            return FakeProvider(payload=payload, **kwargs)

        provider_registry.register(name, factory)
        return name

    img1 = EXAMPLES / "electrical_rc_circuit.png"
    img1_copy = tmp_path / "rc.png"
    img1_copy.write_bytes(img1.read_bytes())
    # Build the golden by running the fake provider once
    name = _register("eval-fake", RC_PAYLOAD)
    diagram = api_parse(img1_copy, provider=name, domain="electrical")
    (tmp_path / "rc.golden.json").write_text(diagram.model_dump_json(indent=2))
    return tmp_path, name


def test_diff_perfect_match(dataset_dir):
    tmp_path, name = dataset_dir
    img = tmp_path / "rc.png"
    diagram = api_parse(img, provider=name, domain="electrical")
    from schemagraph.ir.schema import Diagram

    gold = Diagram.model_validate_json((tmp_path / "rc.golden.json").read_text())
    metrics, _pairs = diff_diagrams(diagram, gold)
    assert metrics.node_f1 == 1.0
    assert metrics.edge_f1 == 1.0
    assert metrics.label_accuracy == 1.0


def test_diff_partial_overlap():
    from schemagraph.ir.schema import (
        Diagram,
        Edge,
        Node,
        Provenance,
        SourceMeta,
    )

    prov = Provenance(stage="user", producer="t")
    a = Node(id="a", kind="resistor", label="R", provenance=prov)
    b = Node(id="b", kind="capacitor", label="C", provenance=prov)
    extra = Node(id="x", kind="inductor", label="L", provenance=prov)

    gold = Diagram(
        id="g",
        source=SourceMeta(),
        nodes=[a, b],
        edges=[Edge(id="e", source="a", target="b", kind="wire", provenance=prov)],
    )
    pred = Diagram(
        id="p",
        source=SourceMeta(),
        nodes=[a, b, extra],
        edges=[Edge(id="e2", source="a", target="b", kind="wire", provenance=prov)],
    )
    metrics, _ = diff_diagrams(pred, gold)
    assert metrics.nodes_matched == 2
    assert metrics.nodes_pred == 3
    assert metrics.nodes_gold == 2
    assert 0.5 < metrics.node_f1 < 1.0
    assert metrics.edge_f1 == 1.0


def test_evaluate_dataset_and_render(dataset_dir, tmp_path):
    ds_dir, name = dataset_dir
    report = evaluate_dataset(ds_dir, provider=name, domain="electrical")
    assert len(report.fixtures) == 1
    assert report.fixtures[0].metrics.node_f1 == 1.0
    html = render_html(report)
    assert "<html" in html
    assert "node f1" in html.lower()


def test_metrics_merge():
    a = Metrics(nodes_pred=2, nodes_gold=2, nodes_matched=2)
    b = Metrics(nodes_pred=4, nodes_gold=3, nodes_matched=2)
    m = a.merged(b)
    assert m.nodes_pred == 6
    assert m.nodes_gold == 5
    assert m.nodes_matched == 4
