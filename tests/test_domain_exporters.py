"""Tests for built-in domain exporters (SPICE, URDF, Modelica, FEniCS, OpenFOAM, orbital)."""

from __future__ import annotations

import json
from pathlib import Path

import schemagraph  # noqa: F401 - ensures registries populate
from schemagraph.api import annotate as api_annotate
from schemagraph.api import export as api_export
from schemagraph.api import parse as api_parse
from schemagraph.ir.schema import (
    Diagram,
    Edge,
    Node,
    Provenance,
    Quantity,
    SourceMeta,
)
from schemagraph.registry import exporter_registry, provider_registry
from schemagraph.vlm.fake_provider import FakeProvider


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_all_domain_exporters_registered():
    names = set(exporter_registry.names())
    for n in ("spice", "urdf", "modelica", "fenics", "openfoam", "orbital"):
        assert n in names, f"missing exporter {n!r}"


# ---------------------------------------------------------------------------
# SPICE
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
}


def _rc_diagram():
    if not (EXAMPLES / "electrical_rc_circuit.png").exists():
        from examples.generate_fixtures import main as gen

        gen()

    def factory(**kwargs):
        return FakeProvider(payload=RC_PAYLOAD, **kwargs)

    provider_registry.register("fake-domain", factory)
    diagram = api_parse(EXAMPLES / "electrical_rc_circuit.png", provider="fake-domain", domain="electrical")
    return api_annotate(diagram, domain="electrical")


def test_spice_exports_netlist():
    diagram = _rc_diagram()
    text = api_export(diagram, format="spice")
    assert "* schemagraph SPICE export" in text
    # Should include one R, one C, one V line
    assert any(line.startswith("R") for line in text.splitlines())
    assert any(line.startswith("C") for line in text.splitlines())
    assert any(line.startswith("V") for line in text.splitlines())
    # Net 0 must be referenced (ground) at least once
    assert any(" 0 " in line or line.endswith(" 0") for line in text.splitlines())
    assert text.strip().endswith(".end")


def test_spice_values_converted_to_si():
    diagram = _rc_diagram()
    text = api_export(diagram, format="spice")
    # 10kΩ -> 10000 ohms, 1uF -> 1e-6 F
    assert "10000" in text
    assert "1e-06" in text or "1e-6" in text


# ---------------------------------------------------------------------------
# URDF
# ---------------------------------------------------------------------------


def test_urdf_emits_links_and_joints():
    prov = Provenance(stage="user", producer="t")
    nodes = [
        Node(id="L1", kind="link", label="L1", domain="mechanical", provenance=prov, properties={"mass": Quantity(value=1.0, unit="kilogram")}),
        Node(id="L2", kind="link", label="L2", domain="mechanical", provenance=prov, properties={"mass": Quantity(value=2.0, unit="kilogram")}),
    ]
    edges = [Edge(id="J1", source="L1", target="L2", kind="revolute", domain="mechanical", provenance=prov)]
    diagram = Diagram(id="d", source=SourceMeta(), nodes=nodes, edges=edges, domain="mechanical")
    text = api_export(diagram, format="urdf")
    assert "<robot" in text
    assert 'name="L1"' in text and 'name="L2"' in text
    assert 'type="revolute"' in text
    assert "parent" in text and "child" in text


# ---------------------------------------------------------------------------
# Modelica
# ---------------------------------------------------------------------------


def test_modelica_emits_components_and_connections():
    diagram = _rc_diagram()
    text = api_export(diagram, format="modelica")
    assert text.startswith("model ")
    assert "Modelica.Electrical.Analog.Basic.Resistor" in text
    assert "Modelica.Electrical.Analog.Basic.Capacitor" in text
    assert "connect(" in text


# ---------------------------------------------------------------------------
# FEniCS
# ---------------------------------------------------------------------------


def test_fenics_emits_runnable_skeleton():
    diagram = _rc_diagram()
    text = api_export(diagram, format="fenics")
    assert "import dolfinx" in text
    assert "def build_problem" in text
    assert 'if __name__ == "__main__":' in text


# ---------------------------------------------------------------------------
# OpenFOAM
# ---------------------------------------------------------------------------


def test_openfoam_writes_case_directory(tmp_path):
    diagram = _rc_diagram()
    out = api_export(diagram, format="openfoam", path=tmp_path / "case")
    case = Path(out)
    assert case.is_dir()
    assert (case / "system" / "controlDict").exists()
    assert (case / "system" / "blockMeshDict").exists()
    assert (case / "0" / "U").exists()


# ---------------------------------------------------------------------------
# Orbital
# ---------------------------------------------------------------------------


def test_orbital_extracts_bodies_and_orbits():
    prov = Provenance(stage="user", producer="t")
    nodes = [
        Node(
            id="earth",
            kind="planet",
            label="Earth",
            properties={"mass": Quantity(value=5.972e24, unit="kilogram"), "radius": Quantity(value=6371.0, unit="km")},
            provenance=prov,
        ),
        Node(
            id="iss",
            kind="orbit",
            label="ISS",
            properties={
                "semi_major_axis": Quantity(value=6781.0, unit="km"),
                "eccentricity": Quantity(value=0.0001),
                "inclination": Quantity(value=51.6, unit="deg"),
            },
            provenance=prov,
        ),
    ]
    diagram = Diagram(id="d", source=SourceMeta(), nodes=nodes, domain="orbital")
    text = api_export(diagram, format="orbital")
    doc = json.loads(text)
    assert any(b["name"] == "Earth" for b in doc["bodies"])
    assert any(o["label"] == "ISS" for o in doc["orbits"])
    elements = doc["orbits"][0]["elements"]
    assert elements["semi_major_axis"]["unit"] == "km"
