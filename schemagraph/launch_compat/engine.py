"""Launch Physics Engine orchestrator."""

from __future__ import annotations

from typing import Any

from schemagraph.launch_compat.assembler import assemble_spacecraft
from schemagraph.launch_compat.models import ENGINE_VERSION, LaunchContext
from schemagraph.launch_compat.report import build_report
from schemagraph.launch_compat.tests import suite as _suite  # noqa: F401 — register tests
from schemagraph.launch_compat.tests.registry import run_all, run_test
from schemagraph.launch_compat.vehicles.loader import get_vehicle, list_launch_vehicles


def _diagram_dict(diagram: Any) -> dict[str, Any] | None:
    if diagram is None:
        return None
    if isinstance(diagram, dict):
        return diagram
    if hasattr(diagram, "model_dump"):
        return diagram.model_dump(mode="json")
    return None


class LaunchPhysicsEngine:
    @staticmethod
    def run_suite(
        *,
        vehicle_id: str,
        orbit: str = "leo",
        profile: dict[str, Any] | None = None,
        annotations: list[Any] | None = None,
        diagram: Any = None,
        load_overrides: dict[str, Any] | None = None,
        test_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        profile = profile or {}
        annotations = annotations or []
        vehicle = get_vehicle(vehicle_id)
        ctx = LaunchContext(
            vehicle_id=vehicle.id,
            orbit=orbit.lower(),
            profile=profile,
            annotations=annotations,
            diagram=_diagram_dict(diagram),
            load_overrides=load_overrides or {},
        )
        spacecraft = assemble_spacecraft(profile, annotations, ctx.diagram)
        results = run_all(ctx, spacecraft, vehicle, test_ids=test_ids)

        stress_field: dict[str, Any] = {}
        for r in results:
            if r.id == "structural_stress" and r.artifacts.get("stress_field"):
                stress_field = r.artifacts["stress_field"]
                break

        sc_summary = {
            "total_mass_kg": spacecraft.total_mass_kg,
            "mass_source": spacecraft.mass_source,
            "cg_mm": [spacecraft.cg_x_m * 1000, spacecraft.cg_y_m * 1000, spacecraft.cg_z_m * 1000],
            "deployable_span_m": spacecraft.deployable_span_m,
            "parts_count": len(spacecraft.parts),
            "beam_members": len(spacecraft.beam_members),
            "missing_structural_parts": spacecraft.missing_structural_parts,
        }

        report = build_report(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            vehicle_data_rev=vehicle.data_rev,
            orbit=ctx.orbit,
            spacecraft_summary=sc_summary,
            results=results,
            stress_field=stress_field,
        )

        # Legacy fields for existing UI
        cap = vehicle.leo_capacity_kg if ctx.orbit == "leo" else (
            vehicle.gto_capacity_kg if ctx.orbit == "gto" else vehicle.sso_capacity_kg
        )
        mass_margin = (cap - spacecraft.total_mass_kg) / cap if cap > 0 else -1
        report["payload_mass_kg"] = round(spacecraft.total_mass_kg, 2)
        report["mass_source"] = spacecraft.mass_source
        report["capacity_kg"] = cap
        report["mass_margin_pct"] = round(mass_margin * 100, 1)
        report["mass_properties"] = {
            "cg_x": spacecraft.cg_x_m,
            "cg_y": spacecraft.cg_y_m,
            "cg_z": spacecraft.cg_z_m,
            "lateral_offset_mm": spacecraft.lateral_offset_mm,
            "moi_ixx": spacecraft.moi_ixx,
            "moi_iyy": spacecraft.moi_iyy,
            "moi_izz": spacecraft.moi_izz,
        }
        return report

    @staticmethod
    def run_one(
        *,
        vehicle_id: str,
        test_id: str,
        orbit: str = "leo",
        profile: dict[str, Any] | None = None,
        annotations: list[Any] | None = None,
        diagram: Any = None,
        load_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = profile or {}
        vehicle = get_vehicle(vehicle_id)
        ctx = LaunchContext(
            vehicle_id=vehicle.id,
            orbit=orbit.lower(),
            profile=profile or {},
            annotations=annotations or [],
            diagram=_diagram_dict(diagram),
            load_overrides=load_overrides or {},
        )
        spacecraft = assemble_spacecraft(profile, annotations or [], ctx.diagram)
        result = run_test(test_id, ctx, spacecraft, vehicle)
        return result.to_check_dict()


def compute_launch_compatibility(
    *,
    vehicle_id: str,
    orbit: str = "leo",
    profile: dict[str, Any] | None = None,
    annotations: list[Any] | None = None,
    diagram: Any = None,
    load_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point."""
    return LaunchPhysicsEngine.run_suite(
        vehicle_id=vehicle_id,
        orbit=orbit,
        profile=profile,
        annotations=annotations,
        diagram=diagram,
        load_overrides=load_overrides,
    )
