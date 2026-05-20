"""Load versioned launch vehicle MPE JSON bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent


@dataclass
class VehicleBundle:
    id: str
    name: str
    provider: str
    schema_version: int
    source_document: str
    rev_date: str
    leo_capacity_kg: float
    gto_capacity_kg: float
    sso_capacity_kg: float
    fairing_diameter_m: float
    fairing_height_m: float
    static_envelope_diameter_m: float
    dynamic_envelope_diameter_m: float
    dynamic_envelope_scale: float
    max_axial_g: float
    max_lateral_g: float
    fairing_acoustic_oaspl_db: float
    depressurization_max_pa_per_s: float
    isp_vac_s: float
    vehicle_dry_mass_kg: float
    propellant_mass_kg: float
    modal_guidance: dict[str, Any] = field(default_factory=dict)
    cg_limits: dict[str, Any] = field(default_factory=dict)
    interface_types: list[str] = field(default_factory=list)
    quasi_static_by_mass_class: list[dict[str, Any]] = field(default_factory=list)
    sine_peaks: list[dict[str, Any]] = field(default_factory=list)
    random_psd: list[dict[str, Any]] = field(default_factory=list)
    shock_srs: list[dict[str, Any]] = field(default_factory=list)
    thermal: dict[str, Any] = field(default_factory=dict)

    @property
    def data_rev(self) -> str:
        return f"{self.id}:{self.rev_date}:v{self.schema_version}"

    def quasi_static_for_mass(self, mass_kg: float) -> dict[str, float]:
        for row in self.quasi_static_by_mass_class:
            if row["mass_min_kg"] <= mass_kg <= row["mass_max_kg"]:
                return {"axial_g": float(row["axial_g"]), "lateral_g": float(row["lateral_g"])}
        if self.quasi_static_by_mass_class:
            last = self.quasi_static_by_mass_class[-1]
            return {"axial_g": float(last["axial_g"]), "lateral_g": float(last["lateral_g"])}
        return {"axial_g": self.max_axial_g, "lateral_g": self.max_lateral_g}


def _from_dict(d: dict[str, Any]) -> VehicleBundle:
    return VehicleBundle(
        id=d["id"],
        name=d["name"],
        provider=d["provider"],
        schema_version=int(d.get("schema_version", 1)),
        source_document=d.get("source_document", ""),
        rev_date=d.get("rev_date", ""),
        leo_capacity_kg=float(d["leo_capacity_kg"]),
        gto_capacity_kg=float(d.get("gto_capacity_kg", 0)),
        sso_capacity_kg=float(d.get("sso_capacity_kg", d["leo_capacity_kg"] * 0.7)),
        fairing_diameter_m=float(d["fairing_diameter_m"]),
        fairing_height_m=float(d["fairing_height_m"]),
        static_envelope_diameter_m=float(d["static_envelope_diameter_m"]),
        dynamic_envelope_diameter_m=float(d["dynamic_envelope_diameter_m"]),
        dynamic_envelope_scale=float(d.get("dynamic_envelope_scale", 0.94)),
        max_axial_g=float(d["max_axial_g"]),
        max_lateral_g=float(d["max_lateral_g"]),
        fairing_acoustic_oaspl_db=float(d.get("fairing_acoustic_oaspl_db", d.get("fairing_acoustic_db", 140))),
        depressurization_max_pa_per_s=float(d["depressurization_max_pa_per_s"]),
        isp_vac_s=float(d["isp_vac_s"]),
        vehicle_dry_mass_kg=float(d["vehicle_dry_mass_kg"]),
        propellant_mass_kg=float(d["propellant_mass_kg"]),
        modal_guidance=d.get("modal_guidance", {}),
        cg_limits=d.get("cg_limits", {}),
        interface_types=list(d.get("interface_types", [])),
        quasi_static_by_mass_class=list(d.get("quasi_static_by_mass_class", [])),
        sine_peaks=list(d.get("sine_peaks", [])),
        random_psd=list(d.get("random_psd", [])),
        shock_srs=list(d.get("shock_srs", [])),
        thermal=d.get("thermal", {}),
    )


@lru_cache(maxsize=32)
def get_vehicle(vehicle_id: str) -> VehicleBundle:
    path = _DIR / f"{vehicle_id}.json"
    alias = {"f9": "falcon9", "elec": "electron", "a6": "ariane6"}
    if not path.exists():
        path = _DIR / f"{alias.get(vehicle_id, vehicle_id)}.json"
    if not path.exists():
        raise ValueError(f"unknown launch vehicle: {vehicle_id}")
    with path.open(encoding="utf-8") as f:
        return _from_dict(json.load(f))


def orbit_capacity_kg(vehicle: VehicleBundle, orbit: str) -> float:
    o = orbit.lower()
    if o == "gto":
        return vehicle.gto_capacity_kg
    if o == "sso":
        return vehicle.sso_capacity_kg
    return vehicle.leo_capacity_kg


def list_launch_vehicles() -> list[dict[str, Any]]:
    out = []
    for p in sorted(_DIR.glob("*.json")):
        with p.open(encoding="utf-8") as f:
            d = json.load(f)
        out.append(
            {
                "id": d["id"],
                "name": d["name"],
                "provider": d["provider"],
                "leo_capacity_kg": d["leo_capacity_kg"],
                "gto_capacity_kg": d.get("gto_capacity_kg", 0),
                "fairing_diameter_m": d["fairing_diameter_m"],
                "rev_date": d.get("rev_date"),
                "source_document": d.get("source_document"),
            }
        )
    return out
