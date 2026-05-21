"""Build launch readiness JSON + CSV from extracted schematic data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schemagraph.launch_compat.schema.field_catalog import (
    CHECK_CATALOG_COLUMNS,
    COMPONENT_CSV_COLUMNS,
    MISSION_CSV_COLUMNS,
    build_check_catalog_rows,
    components_to_annotations,
    compute_check_readiness,
    mission_to_profile,
)

SCHEMA_VERSION = 1
LAUNCH_DIR = "schema/launch"
MANIFEST_NAME = "launch_readiness.json"
LAUNCH_SCHEMA_NAME = "satellite_launch_schema.json"
_BUNDLED_LAUNCH_SCHEMA = Path(__file__).parent / LAUNCH_SCHEMA_NAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_subsystem(name: str, kind: str) -> str:
    n = (name + " " + kind).lower()
    if any(x in n for x in ("solar", "array", "panel", "power")):
        return "Power"
    if any(x in n for x in ("thruster", "prop", "tank")):
        return "Propulsion"
    if any(x in n for x in ("antenna", "comm", "xmit")):
        return "Communications"
    if any(x in n for x in ("wheel", "adcs", "star", "gps")):
        return "ADCS"
    if any(x in n for x in ("bus", "frame", "structure", "deck")):
        return "Structure"
    if any(x in n for x in ("payload", "instrument", "camera")):
        return "Payload"
    return "Other"


def _component_from_annotation(ann: dict[str, Any], node: dict[str, Any] | None) -> dict[str, Any]:
    bbox = ann.get("bbox") or {}
    name = ann.get("name") or (node or {}).get("label") or "component"
    kind = (node or {}).get("kind") or ""
    l = ann.get("length_m")
    w = ann.get("width_m")
    h = ann.get("height_m")
    if bbox and (l is None or l <= 0):
        l = float(bbox.get("w", 40)) * 0.001
        w = float(bbox.get("h", 30)) * 0.001
        h = float(ann.get("height_m") or min(l, w) * 0.5)
    row: dict[str, Any] = {
        "component_id": ann.get("id") or ann.get("node_id") or name,
        "node_id": ann.get("node_id"),
        "name": name,
        "subsystem": _infer_subsystem(name, kind),
        "kind": kind,
        "mass_kg": ann.get("mass_kg"),
        "length_m": l,
        "width_m": w,
        "height_m": h,
        "depth_m": ann.get("depth_m"),
        "volume_m3": ann.get("volume_m3"),
        "power_w": ann.get("power_w"),
        "material": ann.get("material") or "aluminum",
        "bbox_x_px": bbox.get("x"),
        "bbox_y_px": bbox.get("y"),
        "bbox_w_px": bbox.get("w"),
        "bbox_h_px": bbox.get("h"),
        "notes": ann.get("notes"),
    }
    return row


def _default_mission(
    project_id: str,
    project_name: str,
    *,
    total_mass: float | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = profile or {}
    mass = total_mass or p.get("mass_kg")
    return {
        "mass_kg": mass,
        "orbit_altitude_km": p.get("orbit_altitude_km") or 550,
        "orbit_inclination_deg": p.get("orbit_inclination_deg") or 97.4,
        "power_budget_w": p.get("power_budget_w"),
        "fairing_diameter_m": p.get("fairing_diameter_m") or 2.2,
        "deployable_span_m": p.get("deployable_span_m") or 2.0,
        "design_life_years": p.get("design_life_years") or 3,
        "cg_x_mm": p.get("cg_x_mm") or 0,
        "cg_y_mm": p.get("cg_y_mm") or 0,
        "cg_z_mm": p.get("cg_z_mm") or 450,
        "moi_ixx_kgm2": p.get("moi_ixx_kgm2"),
        "moi_iyy_kgm2": p.get("moi_iyy_kgm2"),
        "moi_izz_kgm2": p.get("moi_izz_kgm2"),
        "interface_type": p.get("interface_type") or "paf_1575",
        "primary_lateral_hz": p.get("primary_lateral_hz"),
        "primary_axial_hz": p.get("primary_axial_hz"),
        "vent_area_m2": p.get("vent_area_m2"),
        "sealed_volume_m3": p.get("sealed_volume_m3"),
        "max_q_pa": p.get("max_q_pa"),
        "factor_of_safety_structural": p.get("factor_of_safety_structural") or 2,
        "preferred_vehicle_id": p.get("preferred_vehicle_id") or "f9",
        "target_orbit": p.get("target_orbit") or "sso",
    }


def build_launch_readiness(
    *,
    project_id: str,
    project_name: str,
    diagram: dict[str, Any] | None,
    annotations: list[Any],
    profile: dict[str, Any] | None = None,
    extraction_source: str = "schematic_parse",
) -> dict[str, Any]:
    """Merge IR + annotations into launch readiness document."""
    nodes = {
        str(n["id"]): n
        for n in (diagram or {}).get("nodes") or []
        if isinstance(n, dict) and n.get("id")
    }
    ann_list = [a if isinstance(a, dict) else a.model_dump(mode="json") for a in annotations]
    components: list[dict[str, Any]] = []
    used_nodes: set[str] = set()

    for ann in ann_list:
        nid = ann.get("node_id")
        node = nodes.get(str(nid)) if nid else None
        if nid:
            used_nodes.add(str(nid))
        components.append(_component_from_annotation(ann, node))

    for nid, node in nodes.items():
        if nid in used_nodes:
            continue
        label = node.get("label") or nid
        components.append(
            {
                "component_id": nid,
                "node_id": nid,
                "name": label,
                "subsystem": _infer_subsystem(str(label), str(node.get("kind") or "")),
                "kind": node.get("kind") or "",
                "mass_kg": None,
                "length_m": None,
                "width_m": None,
                "height_m": None,
                "material": None,
            }
        )

    total_mass = sum(c["mass_kg"] for c in components if c.get("mass_kg"))
    mission = _default_mission(project_id, project_name, total_mass=total_mass or None, profile=profile)
    if profile and profile.get("mass_kg"):
        mission["mass_kg"] = profile["mass_kg"]

    readiness = compute_check_readiness(mission, components)
    prefs = {
        "preferred_vehicle_id": mission.get("preferred_vehicle_id") or "f9",
        "target_orbit": mission.get("target_orbit") or "leo",
    }
    mission_block = {k: v for k, v in mission.items() if k not in ("preferred_vehicle_id", "target_orbit")}

    doc = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "project_name": project_name,
        "updated_at": _now_iso(),
        "extraction_source": extraction_source,
        "mission": mission_block,
        "components": components,
        "launch_vehicle_preferences": prefs,
        "check_readiness": {
            "ready_count": readiness.ready_count,
            "blocked_count": readiness.blocked_count,
            "missing_mission_fields": readiness.missing_mission_fields,
            "missing_component_fields": readiness.missing_component_fields,
            "tests_unblocked": readiness.tests_unblocked,
        },
    }
    return doc


def ensure_launch_schema_reference(project_root: Path) -> str:
    """Copy bundled JSON Schema into project schema/launch/ for explorer preview."""
    rel = f"schema/launch/{LAUNCH_SCHEMA_NAME}"
    launch_dir = project_root / "schema" / "launch"
    launch_dir.mkdir(parents=True, exist_ok=True)
    dst = launch_dir / LAUNCH_SCHEMA_NAME
    if _BUNDLED_LAUNCH_SCHEMA.is_file():
        dst.write_text(_BUNDLED_LAUNCH_SCHEMA.read_text(encoding="utf-8"), encoding="utf-8")
    return rel


def write_launch_csv_files(project_root: Path, doc: dict[str, Any]) -> dict[str, str]:
    """Write launch CSVs under project schema/launch/. Returns relative paths."""
    import csv

    launch_dir = project_root / "schema" / "launch"
    launch_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    mission = doc.get("mission") or {}
    prefs = doc.get("launch_vehicle_preferences") or {}
    mission_row = {"project_id": doc["project_id"], "project_name": doc["project_name"], **mission}
    mission_row["preferred_vehicle_id"] = prefs.get("preferred_vehicle_id", "")
    mission_row["target_orbit"] = prefs.get("target_orbit", "")

    mpath = launch_dir / "launch_mission.csv"
    with mpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MISSION_CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerow({c: mission_row.get(c, "") for c in MISSION_CSV_COLUMNS})
    files["launch_mission"] = "schema/launch/launch_mission.csv"

    components = doc.get("components") or []
    cpath = launch_dir / "launch_components.csv"
    with cpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COMPONENT_CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in components:
            w.writerow({c: row.get(c, "") for c in COMPONENT_CSV_COLUMNS})
    files["launch_components"] = "schema/launch/launch_components.csv"

    catalog = build_check_catalog_rows()
    cat_path = launch_dir / "launch_check_catalog.csv"
    with cat_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CHECK_CATALOG_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in catalog:
            w.writerow(row)
    files["launch_check_catalog"] = "schema/launch/launch_check_catalog.csv"

    return files


def attach_launch_to_registry(project_id: str, doc: dict[str, Any], registry_doc: dict[str, Any]) -> dict[str, Any]:
    """Merge launch readiness into satellite_schema manifest."""
    from server.workspace import project_dir

    root = project_dir(project_id)
    launch_files = write_launch_csv_files(root, doc)
    launch_files["launch_schema"] = ensure_launch_schema_reference(root)
    launch_manifest_path = root / "schema" / "launch" / MANIFEST_NAME
    launch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    launch_manifest_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    registry_doc = dict(registry_doc)
    registry_doc["launch_readiness"] = {
        "schema_version": SCHEMA_VERSION,
        "manifest": f"schema/launch/{MANIFEST_NAME}",
        "files": launch_files,
        "check_readiness": doc.get("check_readiness"),
    }
    if "files" not in registry_doc:
        registry_doc["files"] = {}
    registry_doc["files"].update(launch_files)
    return registry_doc


def load_launch_readiness(project_id: str) -> dict[str, Any] | None:
    from server.workspace import project_dir

    p = project_dir(project_id) / "schema" / "launch" / MANIFEST_NAME
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def profile_and_annotations_from_launch(project_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    doc = load_launch_readiness(project_id)
    if not doc:
        return {}, []
    return mission_to_profile(doc.get("mission") or {}), components_to_annotations(
        doc.get("components") or []
    )
