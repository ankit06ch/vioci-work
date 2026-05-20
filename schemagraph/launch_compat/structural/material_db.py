"""Material properties for structural allowables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialProps:
    name: str
    e_pa: float
    rho_kg_m3: float
    yield_stress_pa: float
    allowable_stress_pa: float


MATERIALS: dict[str, MaterialProps] = {
    "aluminum": MaterialProps("aluminum", 69e9, 2700, 275e6, 137e6),
    "aluminium": MaterialProps("aluminium", 69e9, 2700, 275e6, 137e6),
    "al 6061": MaterialProps("al 6061", 68.9e9, 2700, 275e6, 124e6),
    "al 7075": MaterialProps("al 7075", 71.7e9, 2810, 503e6, 228e6),
    "carbon fiber": MaterialProps("carbon fiber", 135e9, 1600, 600e6, 300e6),
    "cfrp": MaterialProps("cfrp", 135e9, 1600, 600e6, 300e6),
    "steel": MaterialProps("steel", 200e9, 7850, 350e6, 175e6),
    "titanium": MaterialProps("titanium", 110e9, 4500, 880e6, 440e6),
    "composite": MaterialProps("composite", 100e9, 1800, 500e6, 250e6),
    "generic": MaterialProps("generic", 70e9, 2700, 250e6, 125e6),
}


def lookup_material(name: str | None) -> MaterialProps:
    if not name:
        return MATERIALS["generic"]
    key = name.strip().lower()
    if key in MATERIALS:
        return MATERIALS[key]
    for k, v in MATERIALS.items():
        if k in key or key in k:
            return v
    return MATERIALS["generic"]
