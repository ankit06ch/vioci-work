"""End-to-end pipeline test: image -> IR -> exports.

Uses the FakeProvider so we don't touch the network in CI.
"""

from __future__ import annotations

import io
import json
import pickle
from pathlib import Path

import pytest

from schemagraph.api import annotate as api_annotate
from schemagraph.api import export as api_export
from schemagraph.api import parse as api_parse
from schemagraph.api import validate as api_validate
from schemagraph.registry import provider_registry
from schemagraph.vlm.fake_provider import FakeProvider


@pytest.fixture
def register_fake(fake_vlm_payload):
    def factory(**kwargs):
        return FakeProvider(payload=fake_vlm_payload, **kwargs)

    provider_registry.register("fake", factory)
    yield "fake"


@pytest.fixture
def tmp_png(tmp_path: Path, small_rc_circuit_png: bytes) -> Path:
    p = tmp_path / "rc.png"
    p.write_bytes(small_rc_circuit_png)
    return p


def test_parse_validates_and_exports_all_formats(tmp_png, tmp_path, register_fake):
    diagram = api_parse(tmp_png, provider=register_fake, domain="electrical")

    # Basic structure
    assert len(diagram.nodes) >= 3  # R1, C1, GND
    assert len(diagram.edges) >= 1
    assert diagram.domain == "electrical"
    # Stable IDs
    assert diagram.id.startswith("dgm_")
    for n in diagram.nodes:
        assert n.id.startswith("n_")

    # Validation should pass
    report = api_validate(diagram)
    assert report.ok, report.issues

    # Annotation applies unit-aware quantity coercion
    annotated = api_annotate(diagram, domain="electrical")
    resistor = [n for n in annotated.nodes if n.kind == "resistor"][0]
    val = resistor.properties.get("value")
    assert val is not None
    # "10kΩ" -> 10000 ohm
    assert hasattr(val, "value") and abs(val.value - 10000.0) < 1.0
    assert val.unit and "ohm" in val.unit

    # NetworkX export
    nx_path = tmp_path / "g.gpickle"
    api_export(annotated, format="networkx", path=nx_path)
    with open(nx_path, "rb") as fh:
        G = pickle.load(fh)
    assert G.number_of_nodes() == len(annotated.nodes)
    assert G.number_of_edges() == len(annotated.edges)

    # GraphML export
    gml_path = tmp_path / "g.graphml"
    api_export(annotated, format="graphml", path=gml_path)
    text = gml_path.read_text()
    assert "<graphml" in text
    for n in annotated.nodes:
        assert n.id in text

    # JSON-LD export
    ld_path = tmp_path / "g.jsonld"
    api_export(annotated, format="jsonld", path=ld_path)
    doc = json.loads(ld_path.read_text())
    assert doc["@context"]["sg"].startswith("https://")
    assert len(doc["nodes"]) == len(annotated.nodes)
    assert any(n.get("kind") == "resistor" for n in doc["nodes"])


def test_parse_is_deterministic(tmp_png, register_fake):
    a = api_parse(tmp_png, provider=register_fake)
    b = api_parse(tmp_png, provider=register_fake)
    assert a.id == b.id
    assert {n.id for n in a.nodes} == {n.id for n in b.nodes}
    assert {e.id for e in a.edges} == {e.id for e in b.edges}
