"""Launch integration engine tests."""

from __future__ import annotations

import pytest

from schemagraph.launch_compat import compute_launch_compatibility
from schemagraph.launch_compat.vehicles import VEHICLES


def _ann(name: str, mass: float, x: float, y: float, power: float = 0.0) -> dict:
    return {
        "id": name,
        "node_id": name,
        "name": name,
        "bbox": {"x": x, "y": y, "w": 40, "h": 30},
        "mass_kg": mass,
        "power_w": power,
    }


def test_electron_rejects_heavy_payload():
    r = compute_launch_compatibility(
        vehicle_id="elec",
        orbit="leo",
        profile={"mass_kg": 500},
        annotations=[],
    )
    assert r["overall_status"] in ("fail", "caution", "review")
    assert r["payload_mass_kg"] == 500
    mass_check = next(c for c in r["checks"] if c["id"] == "mass_capacity")
    assert mass_check["status"] == "fail"
    assert r["overall_score"] < 85


def test_falcon_nominal_light_satellite():
    r = compute_launch_compatibility(
        vehicle_id="f9",
        orbit="leo",
        profile={"mass_kg": 800, "deployable_span_m": 3.5, "fairing_diameter_m": 2.0},
        annotations=[
            _ann("bus", 400, 100, 100, 50),
            _ann("solar", 200, 200, 80, 120),
            _ann("payload", 200, 150, 150, 30),
        ],
    )
    assert r["overall_score"] >= 70
    assert r["stress_field"]["max_stress_mpa"] > 0
    assert len(r["stress_field"]["hotspots"]) >= 1


def test_stress_hotspots_ordered():
    r = compute_launch_compatibility(
        vehicle_id="f9",
        orbit="leo",
        profile={"mass_kg": 1200},
        annotations=[_ann("heavy", 800, 50, 50, 200)],
    )
    hs = r["stress_field"]["hotspots"]
    assert hs[0]["stress_mpa"] >= hs[-1]["stress_mpa"]


def test_unknown_vehicle():
    with pytest.raises(ValueError):
        compute_launch_compatibility(vehicle_id="nope", orbit="leo")


def test_all_catalog_vehicles():
    for vid in VEHICLES:
        r = compute_launch_compatibility(vehicle_id=vid, orbit="leo", profile={"mass_kg": 100})
        assert r["vehicle_id"] == vid
