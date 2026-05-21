"""Launch readiness JSON schema, builder, and CSV export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemagraph.launch_compat.schema.builder import (
    build_launch_readiness,
    write_launch_csv_files,
)
from schemagraph.launch_compat.schema.field_catalog import (
    compute_check_readiness,
    mission_to_profile,
    components_to_annotations,
)
from schemagraph.launch_compat.schema.validate import load_schema, validate_document

SAMPLES = Path(__file__).resolve().parents[1] / "schemagraph" / "launch_compat" / "schema" / "samples"
LANDSAT = SAMPLES / "landsat_telemetry_bus.json"
VIOCI_DEMO = SAMPLES / "vioci_leo_observation_sat.json"


@pytest.fixture
def landsat_doc() -> dict:
    return json.loads(LANDSAT.read_text(encoding="utf-8"))


def test_schema_loads():
    schema = load_schema()
    assert schema["title"] == "SatelliteLaunchReadiness"
    assert schema["properties"]["mission"]["$ref"] == "#/$defs/Mission"


def test_landsat_sample_validates(landsat_doc):
    ok, errors = validate_document(landsat_doc)
    assert ok, errors


def test_landsat_unblocks_full_suite(landsat_doc):
    r = compute_check_readiness(landsat_doc["mission"], landsat_doc["components"])
    # emc_rf stays blocked until spectrum data exists in schema
    assert r.blocked_count <= 1
    assert "emc_rf" not in r.tests_unblocked
    assert r.ready_count >= 15
    assert "structural_stress" in r.tests_unblocked


def test_write_launch_csvs(tmp_path, landsat_doc):
    files = write_launch_csv_files(tmp_path, landsat_doc)
    assert (tmp_path / "schema" / "launch" / "launch_mission.csv").is_file()
    assert (tmp_path / "schema" / "launch" / "launch_components.csv").is_file()
    assert (tmp_path / "schema" / "launch" / "launch_check_catalog.csv").is_file()
    assert "launch_mission" in files
    mission_text = (tmp_path / "schema" / "launch" / "launch_mission.csv").read_text()
    assert "847" in mission_text
    comp_text = (tmp_path / "schema" / "launch" / "launch_components.csv").read_text()
    assert "bus_primary" in comp_text


def test_build_from_annotations():
    diagram = {
        "nodes": [
            {"id": "n1", "label": "Solar Panel", "kind": "panel"},
            {"id": "n2", "label": "Bus Deck", "kind": "frame"},
        ]
    }
    annotations = [
        {
            "id": "a1",
            "node_id": "n1",
            "name": "Solar Panel",
            "mass_kg": 50,
            "length_m": 2.0,
            "width_m": 1.0,
            "height_m": 0.05,
            "material": "composite",
        },
        {
            "id": "a2",
            "node_id": "n2",
            "name": "Bus Deck",
            "mass_kg": 200,
            "length_m": 1.0,
            "width_m": 1.0,
            "height_m": 0.2,
            "material": "aluminum",
        },
    ]
    doc = build_launch_readiness(
        project_id="p1",
        project_name="Test Sat",
        diagram=diagram,
        annotations=annotations,
        profile={"mass_kg": 250, "orbit_altitude_km": 550},
    )
    assert doc["mission"]["mass_kg"] == 250
    assert len(doc["components"]) == 2
    assert doc["check_readiness"]["ready_count"] > 0


def test_vioci_demo_runs_launch_suite():
    """Sample fixture should drive a full (non-blocked) physics suite run."""
    from schemagraph.launch_compat import LaunchPhysicsEngine

    doc = json.loads(VIOCI_DEMO.read_text(encoding="utf-8"))
    r = LaunchPhysicsEngine.run_suite(
        vehicle_id="f9",
        orbit="sso",
        profile=mission_to_profile(doc["mission"]),
        annotations=components_to_annotations(doc["components"]),
        diagram=None,
    )
    statuses = {t["id"]: t["test_status"] for t in r["tests"]}
    assert statuses["mass_capacity"] != "blocked"
    assert statuses["structural_stress"] != "blocked"
    assert statuses["emc_rf"] == "blocked"
    assert len([s for s in statuses.values() if s != "blocked"]) >= 14


def test_mission_to_profile_roundtrip(landsat_doc):
    profile = mission_to_profile(landsat_doc["mission"])
    assert profile["mass_kg"] == 847
    anns = components_to_annotations(landsat_doc["components"])
    assert len(anns) == len(landsat_doc["components"])
    assert anns[0]["mass_kg"] == 285
