"""Consolidated launch physics audit report."""

from __future__ import annotations

from typing import Any

from schemagraph.launch_compat.models import ENGINE_NAME, ENGINE_VERSION, OverallStatus, PhysicsTestResult


def build_report(
    *,
    vehicle_id: str,
    vehicle_name: str,
    vehicle_data_rev: str,
    orbit: str,
    spacecraft_summary: dict[str, Any],
    results: list[PhysicsTestResult],
    stress_field: dict[str, Any] | None,
) -> dict[str, Any]:
    mandatory = [r for r in results if r.mandatory]
    blockers = [r for r in results if r.status in ("fail", "blocked") and r.mandatory]
    fails = [r for r in results if r.status == "fail"]
    blocked = [r for r in results if r.status == "blocked"]

    if blockers:
        overall_status: OverallStatus = "fail"
    elif fails:
        overall_status = "caution"
    elif any(r.status == "warn" for r in results):
        overall_status = "review"
    else:
        overall_status = "nominal"

    scores: dict[str, list[float]] = {}
    for r in results:
        if r.status == "blocked":
            pts = 0.0
        elif r.status == "pass":
            pts = 100.0
        elif r.status == "warn":
            pts = 65.0
        else:
            pts = 15.0
        scores.setdefault(r.category, []).append(pts)
    category_scores = {k: round(sum(v) / len(v)) for k, v in scores.items()}

    overall_score = round(sum(category_scores.values()) / max(len(category_scores), 1))

    warnings = []
    for r in results:
        if r.status in ("fail", "warn", "blocked"):
            level = "crit" if r.status == "fail" else ("warn" if r.status == "warn" else "info")
            warnings.append({"level": level, "text": f"{r.title}: {r.detail}", "check_id": r.id})

    tests = [r.to_check_dict() for r in results]

    return {
        "engine_name": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle_name,
        "vehicle_data_rev": vehicle_data_rev,
        "orbit": orbit,
        "overall_score": overall_score,
        "overall_status": overall_status,
        "verdict": "NO-GO" if blockers else ("REVIEW" if fails or blocked else "GO"),
        "blockers": [{"id": r.id, "title": r.title, "status": r.status, "detail": r.detail} for r in blockers],
        "spacecraft": spacecraft_summary,
        "category_scores": category_scores,
        "tests": tests,
        "checks": tests,
        "warnings": warnings,
        "stress_field": stress_field or {},
        "simulation": {
            "engine_name": ENGINE_NAME,
            "engine": ENGINE_VERSION,
            "fea_mode": (stress_field or {}).get("fea_mode", "none"),
            "notes": (
                f"{ENGINE_NAME} analytical mission assurance engine. Flight release requires measured mass properties "
                "and qualification testing. BLOCKED tests indicate missing required inputs."
            ),
        },
        "disclaimer": (
            "Engineering analysis only — not a certification artifact. No silent pass on missing data."
        ),
    }
