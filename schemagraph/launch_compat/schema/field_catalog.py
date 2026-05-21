"""Field catalog: maps schema fields → physics tests and CSV columns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Mission-level fields: field_key -> test ids that require it (empty = advisory only)
MISSION_FIELD_TESTS: dict[str, list[str]] = {
    "mass_kg": ["mass_capacity", "quasi_static_loads", "structural_stress", "orbit_delta_v"],
    "orbit_altitude_km": ["orbit_delta_v", "thermal_ascent", "depressurization"],
    "orbit_inclination_deg": ["orbit_delta_v"],
    "deployable_span_m": ["static_envelope", "dynamic_envelope", "modal_lateral"],
    "fairing_diameter_m": ["static_envelope", "dynamic_envelope"],
    "cg_x_mm": ["center_of_gravity"],
    "cg_y_mm": ["center_of_gravity"],
    "cg_z_mm": ["center_of_gravity"],
    "moi_ixx_kgm2": ["moments_of_inertia"],
    "moi_iyy_kgm2": ["moments_of_inertia"],
    "moi_izz_kgm2": ["moments_of_inertia"],
    "primary_lateral_hz": ["modal_lateral"],
    "primary_axial_hz": ["modal_axial"],
    "vent_area_m2": ["depressurization"],
    "sealed_volume_m3": ["depressurization"],
    "interface_type": ["center_of_gravity"],
    "power_budget_w": [],
}

MISSION_REQUIRED_FOR_FULL_SUITE = [
    "mass_kg",
    "orbit_altitude_km",
    "deployable_span_m",
    "fairing_diameter_m",
]

COMPONENT_REQUIRED_FIELDS = ["component_id", "name", "mass_kg", "length_m", "width_m", "height_m", "material"]

COMPONENT_FIELD_TESTS: dict[str, list[str]] = {
    "mass_kg": ["mass_capacity", "structural_stress", "quasi_static_loads"],
    "length_m": ["structural_stress"],
    "width_m": ["structural_stress"],
    "height_m": ["structural_stress"],
    "material": ["structural_stress"],
    "power_w": ["structural_stress"],
    "bbox_x_px": ["structural_stress", "center_of_gravity"],
}

MISSION_CSV_COLUMNS = [
    "project_id",
    "project_name",
    "mass_kg",
    "orbit_altitude_km",
    "orbit_inclination_deg",
    "power_budget_w",
    "fairing_diameter_m",
    "deployable_span_m",
    "design_life_years",
    "cg_x_mm",
    "cg_y_mm",
    "cg_z_mm",
    "moi_ixx_kgm2",
    "moi_iyy_kgm2",
    "moi_izz_kgm2",
    "interface_type",
    "primary_lateral_hz",
    "primary_axial_hz",
    "vent_area_m2",
    "sealed_volume_m3",
    "max_q_pa",
    "factor_of_safety_structural",
    "preferred_vehicle_id",
    "target_orbit",
]

COMPONENT_CSV_COLUMNS = [
    "component_id",
    "node_id",
    "name",
    "subsystem",
    "kind",
    "mass_kg",
    "length_m",
    "width_m",
    "height_m",
    "depth_m",
    "volume_m3",
    "power_w",
    "material",
    "bbox_x_px",
    "bbox_y_px",
    "bbox_w_px",
    "bbox_h_px",
    "notes",
]

CHECK_CATALOG_COLUMNS = [
    "test_id",
    "category",
    "mandatory",
    "required_level",
    "field_scope",
    "field_key",
    "description",
]


@dataclass
class ReadinessReport:
    ready_count: int
    blocked_count: int
    missing_mission_fields: list[str]
    missing_component_fields: list[str]
    tests_unblocked: list[str]


def _present(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    if isinstance(val, float) and val != val:
        return False
    return True


def compute_check_readiness(mission: dict[str, Any], components: list[dict[str, Any]]) -> ReadinessReport:
    """Determine which tests have minimum data (mission + ≥1 valid component)."""
    from schemagraph.launch_compat.tests.registry import list_tests

    missing_mission = [f for f in MISSION_REQUIRED_FOR_FULL_SUITE if not _present(mission.get(f))]
    comp_ok = any(
        all(_present(c.get(f)) for f in ["mass_kg", "length_m", "width_m", "height_m", "material"])
        for c in components
    )
    missing_comp = [] if comp_ok else ["components[].mass_kg+dimensions+material"]

    # Map fields present → tests satisfied
    fields_present: set[str] = set()
    for k, v in mission.items():
        if _present(v):
            fields_present.add(k)
    if comp_ok:
        fields_present.update(COMPONENT_FIELD_TESTS.keys())

    all_tests = set(list_tests())
    unblocked: set[str] = set()
    for field, tests in {**MISSION_FIELD_TESTS, **COMPONENT_FIELD_TESTS}.items():
        if field in fields_present or (field.startswith("bbox") and comp_ok):
            unblocked.update(tests)

    # Tests that need no extra mission fields beyond defaults
    always = {"acoustic", "sine_vibration", "shock_srs", "random_vibration", "quasi_static_loads"}
    if _present(mission.get("mass_kg")):
        unblocked.update(always)
    if _present(mission.get("orbit_altitude_km")):
        unblocked.add("orbit_delta_v")
        unblocked.add("thermal_ascent")
    if _present(mission.get("vent_area_m2")) and _present(mission.get("sealed_volume_m3")):
        unblocked.add("depressurization")
    unblocked &= all_tests

    blocked = sorted(all_tests - unblocked)
    return ReadinessReport(
        ready_count=len(unblocked),
        blocked_count=len(blocked),
        missing_mission_fields=missing_mission,
        missing_component_fields=missing_comp,
        tests_unblocked=sorted(unblocked),
    )


def build_check_catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, tests in MISSION_FIELD_TESTS.items():
        for tid in tests:
            rows.append(
                {
                    "test_id": tid,
                    "category": tid.split("_")[0],
                    "mandatory": "yes",
                    "required_level": "mission",
                    "field_scope": "mission",
                    "field_key": field,
                    "description": f"Mission field `{field}` required to run {tid}",
                }
            )
    for field, tests in COMPONENT_FIELD_TESTS.items():
        for tid in tests:
            rows.append(
                {
                    "test_id": tid,
                    "category": tid.split("_")[0],
                    "mandatory": "yes" if tid == "structural_stress" else "partial",
                    "required_level": "component",
                    "field_scope": "components[]",
                    "field_key": field,
                    "description": f"Per-part `{field}` for {tid}",
                }
            )
    return rows


def mission_to_profile(mission: dict[str, Any]) -> dict[str, Any]:
    """Convert mission block to SatelliteProfile / launch-compat profile keys."""
    return {k: v for k, v in mission.items() if v is not None and k not in (
        "preferred_vehicle_id",
        "target_orbit",
        "factor_of_safety_structural",
    )}


def components_to_annotations(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert component rows to PartAnnotation-like dicts for assembler."""
    out = []
    for c in components:
        ann: dict[str, Any] = {
            "id": c.get("component_id") or c.get("part_id"),
            "node_id": c.get("node_id"),
            "name": c.get("name"),
            "mass_kg": c.get("mass_kg"),
            "length_m": c.get("length_m"),
            "width_m": c.get("width_m"),
            "height_m": c.get("height_m"),
            "depth_m": c.get("depth_m"),
            "volume_m3": c.get("volume_m3"),
            "power_w": c.get("power_w"),
            "material": c.get("material"),
            "notes": c.get("notes"),
        }
        if _present(c.get("bbox_x_px")):
            ann["bbox"] = {
                "x": float(c["bbox_x_px"]),
                "y": float(c["bbox_y_px"]),
                "w": float(c["bbox_w_px"]),
                "h": float(c["bbox_h_px"]),
            }
        out.append(ann)
    return out
