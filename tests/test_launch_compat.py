"""Launch Physics Engine tests."""

from __future__ import annotations

import pytest

from schemagraph.launch_compat import LaunchPhysicsEngine, compute_launch_compatibility
from schemagraph.launch_compat.loads.parser import parse_load_file, psd_grms
from schemagraph.launch_compat.structural.static_fea import solve_beam_fea
from schemagraph.launch_compat.assembler import assemble_spacecraft
from schemagraph.launch_compat.vehicles.loader import get_vehicle


def _ann(name: str, mass: float, x: float, y: float, l=0.4, w=0.3, h=0.2) -> dict:
    return {
        "id": name,
        "node_id": name,
        "name": name,
        "bbox": {"x": x, "y": y, "w": 40, "h": 30},
        "mass_kg": mass,
        "length_m": l,
        "width_m": w,
        "height_m": h,
        "material": "aluminum",
        "power_w": 10.0,
    }


def test_electron_rejects_heavy_payload():
    r = compute_launch_compatibility(
        vehicle_id="elec",
        orbit="leo",
        profile={"mass_kg": 500},
        annotations=[],
    )
    assert r["verdict"] in ("NO-GO", "REVIEW", "FAIL")
    mass_test = next(t for t in r["tests"] if t["id"] == "mass_capacity")
    assert mass_test["test_status"] == "fail"


def test_falcon_with_structural_parts():
    r = compute_launch_compatibility(
        vehicle_id="f9",
        orbit="leo",
        profile={"mass_kg": 800, "deployable_span_m": 3.5},
        annotations=[
            _ann("bus", 400, 100, 100),
            _ann("solar", 200, 200, 80),
            _ann("payload", 200, 150, 150),
        ],
    )
    assert r["engine_version"] == "launch_physics_v2"
    assert "tests" in r
    struct = next(t for t in r["tests"] if t["id"] == "structural_stress")
    assert struct["test_status"] in ("pass", "warn", "fail")
    assert r["stress_field"].get("fea_mode") == "beam_network_static"


def test_blocked_without_mass():
    r = compute_launch_compatibility(
        vehicle_id="f9",
        orbit="leo",
        profile={},
        annotations=[],
    )
    assert any(b["id"] == "mass_capacity" for b in r.get("blockers", []))


def test_psd_grms():
    pts = [{"freq_hz": 20, "asd_g2_hz": 0.01}, {"freq_hz": 200, "asd_g2_hz": 0.02}]
    g = psd_grms(pts)
    assert g > 0


def test_load_parser_csv():
    csv = "freq_hz,asd_g2_hz\n20,0.01\n100,0.05\n"
    p = parse_load_file("psd", csv)
    assert len(p["points"]) == 2


def test_beam_fea_cantilever_like():
    sc = assemble_spacecraft(
        {"mass_kg": 100},
        [_ann("a", 50, 0, 0), _ann("b", 50, 100, 0)],
    )
    qs = get_vehicle("f9").quasi_static_for_mass(100)
    fea = solve_beam_fea(sc, qs["axial_g"], qs["lateral_g"])
    assert fea["max_stress_mpa"] >= 0
    assert len(fea.get("members", [])) >= 1


def test_single_test_runner():
    r = LaunchPhysicsEngine.run_one(
        vehicle_id="f9",
        test_id="mass_capacity",
        profile={"mass_kg": 500},
        annotations=[],
    )
    assert r["id"] == "mass_capacity"


def test_all_catalog_vehicles():
    for vid in ["f9", "elec", "starship", "vulcan", "a6"]:
        r = compute_launch_compatibility(vehicle_id=vid, orbit="leo", profile={"mass_kg": 100})
        assert r["vehicle_id"] == vid


def test_unknown_vehicle():
    with pytest.raises(ValueError):
        compute_launch_compatibility(vehicle_id="nope", orbit="leo")
