"""Orbital mechanics proxies for mission Δv."""

from __future__ import annotations

import math

G0 = 9.80665
MU_EARTH = 3.986004418e14
R_EARTH = 6_371_000.0


def circular_orbit_velocity(altitude_km: float) -> float:
    r = R_EARTH + altitude_km * 1000.0
    return math.sqrt(MU_EARTH / r)


def delta_v_circular_leo(altitude_km: float = 550.0) -> float:
    """Approximate Δv from surface to circular orbit (with gravity/drag losses)."""
    v_circ = circular_orbit_velocity(altitude_km)
    return v_circ + 1500.0  # drag/gravity loss proxy


def delta_v_plane_change(inc_deg: float, altitude_km: float = 550.0) -> float:
    v = circular_orbit_velocity(altitude_km)
    inc = math.radians(inc_deg)
    return 2 * v * math.sin(inc / 2)


def delta_v_gto(altitude_km: float = 550.0) -> float:
    """LEO to GTO transfer proxy."""
    v_leo = circular_orbit_velocity(altitude_km)
    r_leo = R_EARTH + altitude_km * 1000.0
    r_geo = 42_164_000.0
    v_geo = math.sqrt(MU_EARTH / r_geo)
    a_xfer = (r_leo + r_geo) / 2
    v_peri = math.sqrt(MU_EARTH * (2 / r_leo - 1 / a_xfer))
    v_apo = math.sqrt(MU_EARTH * (2 / r_geo - 1 / a_xfer))
    return abs(v_apo - v_geo) + abs(v_peri - v_leo) + 500.0


def mission_delta_v_required(orbit: str, altitude_km: float, inclination_deg: float) -> float:
    o = orbit.lower()
    if o == "gto":
        return delta_v_gto(altitude_km)
    base = delta_v_circular_leo(altitude_km)
    if o == "sso" and inclination_deg > 0:
        base += delta_v_plane_change(inclination_deg, altitude_km) * 0.5
    elif inclination_deg > 28.5:
        base += delta_v_plane_change(inclination_deg - 28.5, altitude_km) * 0.3
    return base


def vehicle_delta_v(isp_s: float, dry_kg: float, prop_kg: float) -> float:
    m0 = dry_kg + prop_kg
    mf = dry_kg
    if mf <= 0 or m0 <= mf:
        return 0.0
    return isp_s * G0 * math.log(m0 / mf)
