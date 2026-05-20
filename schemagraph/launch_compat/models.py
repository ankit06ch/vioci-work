"""Data models for launch physics engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

TestStatus = Literal["pass", "warn", "fail", "blocked"]
OverallStatus = Literal["nominal", "review", "caution", "fail"]

ENGINE_VERSION = "launch_physics_v2"


@dataclass
class PhysicsTestResult:
    id: str
    category: str
    title: str
    status: TestStatus
    mandatory: bool
    measured: str
    limit: str
    detail: str
    margin: float | None = None
    margin_of_safety: float | None = None
    assumptions: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_check_dict(self) -> dict[str, Any]:
        legacy = "pass" if self.status == "pass" else ("fail" if self.status in ("fail", "blocked") else "warn")
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "status": legacy if self.status != "blocked" else "fail",
            "test_status": self.status,
            "mandatory": self.mandatory,
            "value": self.measured,
            "limit": self.limit,
            "detail": self.detail,
            "margin": self.margin,
            "margin_of_safety": self.margin_of_safety,
            "assumptions": self.assumptions,
            "references": self.references,
        }


@dataclass
class PartMassProperties:
    id: str
    name: str
    mass_kg: float
    cx_m: float
    cy_m: float
    cz_m: float
    length_m: float
    width_m: float
    height_m: float
    power_w: float
    material: str | None
    has_structural_data: bool


@dataclass
class BeamMember:
    id: str
    node_a: int
    node_b: int
    length_m: float
    area_m2: float
    e_pa: float
    allowable_stress_pa: float
    name: str = ""


@dataclass
class SpacecraftModel:
    total_mass_kg: float
    mass_source: str
    parts: list[PartMassProperties]
    cg_x_m: float
    cg_y_m: float
    cg_z_m: float
    moi_ixx: float
    moi_iyy: float
    moi_izz: float
    moi_from_measured: bool
    frame_width_m: float
    frame_height_m: float
    frame_depth_m: float
    deployable_span_m: float
    fairing_diameter_m: float
    beam_members: list[BeamMember] = field(default_factory=list)
    node_positions: list[tuple[float, float, float]] = field(default_factory=list)
    missing_structural_parts: list[str] = field(default_factory=list)

    @property
    def lateral_offset_mm(self) -> float:
        return math.hypot(self.cg_x_m, self.cg_y_m) * 1000


@dataclass
class LaunchContext:
    vehicle_id: str
    orbit: str
    profile: dict[str, Any]
    annotations: list[Any]
    diagram: dict[str, Any] | None
    load_overrides: dict[str, Any]
    factor_of_safety: float = 2.0


def num(profile: dict[str, Any], key: str) -> float | None:
    v = profile.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
