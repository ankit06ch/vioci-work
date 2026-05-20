"""Launch integration checks: mass/orbit, envelope, loads, thermal, stress field."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from schemagraph.launch_compat.vehicles import VEHICLES, LaunchVehicle, orbit_capacity_kg

G0 = 9.80665
DV_LEO = 9_400.0
DV_GTO = 10_500.0
DV_SSO = 9_800.0

CheckStatus = Literal["pass", "warn", "fail"]
OverallStatus = Literal["nominal", "review", "caution", "fail"]

GRID_COLS = 48
GRID_ROWS = 32


@dataclass
class CheckItem:
    id: str
    category: str
    title: str
    status: CheckStatus
    value: str
    limit: str
    detail: str


def list_launch_vehicles() -> list[dict[str, Any]]:
    out = []
    for v in VEHICLES.values():
        out.append(
            {
                "id": v.id,
                "name": v.name,
                "provider": v.provider,
                "leo_capacity_kg": v.leo_capacity_kg,
                "gto_capacity_kg": v.gto_capacity_kg,
                "fairing_diameter_m": v.fairing_diameter_m,
            }
        )
    return sorted(out, key=lambda x: x["name"])


def _num(profile: dict[str, Any], key: str) -> float | None:
    v = profile.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _payload_mass_kg(profile: dict[str, Any], annotations: list[Any]) -> tuple[float, str]:
    pm = _num(profile, "mass_kg")
    if pm is not None and pm > 0:
        return pm, "mission profile"
    masses = []
    for a in annotations:
        m = getattr(a, "mass_kg", None) if not isinstance(a, dict) else a.get("mass_kg")
        if m is not None and not math.isnan(float(m)):
            masses.append(float(m))
    if masses:
        return sum(masses), "annotated parts"
    return 850.0, "default bus estimate"


def _bbox_centroid(a: Any) -> tuple[float, float] | None:
    bbox = getattr(a, "bbox", None) if not isinstance(a, dict) else a.get("bbox")
    if not bbox:
        return None
    if isinstance(bbox, dict):
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    else:
        x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
    return x + w / 2, y + h / 2


def _part_mass(a: Any) -> float:
    m = getattr(a, "mass_kg", None) if not isinstance(a, dict) else a.get("mass_kg")
    return float(m) if m is not None and not math.isnan(float(m)) else 0.0


def _part_power(a: Any) -> float:
    p = getattr(a, "power_w", None) if not isinstance(a, dict) else a.get("power_w")
    return float(p) if p is not None and not math.isnan(float(p)) else 0.0


def _normalize_frame(
    annotations: list[Any],
) -> tuple[float, float, float, float, list[tuple[float, float, float, float, float, str]]]:
    """Return frame bounds and parts as (nx, ny, mass, power, name) in 0..1 coords."""
    parts: list[tuple[float, float, float, float, float, str]] = []
    xs, ys = [], []
    for a in annotations:
        bbox = getattr(a, "bbox", None) if not isinstance(a, dict) else a.get("bbox")
        if not bbox:
            continue
        if isinstance(bbox, dict):
            x, y, w, h = float(bbox["x"]), float(bbox["y"]), float(bbox["w"]), float(bbox["h"])
        else:
            x, y, w, h = float(bbox.x), float(bbox.y), float(bbox.w), float(bbox.h)
        cx, cy = x + w / 2, y + h / 2
        m = _part_mass(a)
        p = _part_power(a)
        name = getattr(a, "name", None) if not isinstance(a, dict) else a.get("name", "part")
        parts.append((cx, cy, m, p, str(name)))
        xs.extend([x, x + w])
        ys.extend([y, y + h])
    if not xs:
        return 0.0, 0.0, 1.0, 1.0, []
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    w = max(xmax - xmin, 1.0)
    h = max(ymax - ymin, 1.0)
    normed = []
    for cx, cy, m, p, name in parts:
        nx = (cx - xmin) / w
        ny = (cy - ymin) / h
        normed.append((nx, ny, m, p, name))
    return xmin, ymin, w, h, normed


def _mass_properties(
    parts: list[tuple[float, float, float, float, str]],
) -> dict[str, float]:
    total_m = sum(p[2] for p in parts)
    if total_m <= 0:
        return {
            "cg_x": 0.5,
            "cg_y": 0.5,
            "moi_pitch": 1.0,
            "moi_yaw": 1.0,
            "lateral_offset_mm": 0.0,
        }
    cg_x = sum(p[0] * p[2] for p in parts) / total_m
    cg_y = sum(p[1] * p[2] for p in parts) / total_m
    moi_pitch = sum(p[2] * (p[1] - cg_y) ** 2 for p in parts)
    moi_yaw = sum(p[2] * (p[0] - cg_x) ** 2 for p in parts)
    lateral_offset_mm = abs(cg_x - 0.5) * 2000 + abs(cg_y - 0.5) * 2000
    return {
        "cg_x": cg_x,
        "cg_y": cg_y,
        "moi_pitch": moi_pitch,
        "moi_yaw": moi_yaw,
        "lateral_offset_mm": lateral_offset_mm,
    }


def _rocket_delta_v(vehicle: LaunchVehicle) -> float:
    m0 = vehicle.vehicle_dry_mass_kg + vehicle.propellant_mass_kg
    mf = vehicle.vehicle_dry_mass_kg
    if mf <= 0 or m0 <= mf:
        return 0.0
    return vehicle.isp_vac_s * G0 * math.log(m0 / mf)


def _build_stress_field(
    parts: list[tuple[float, float, float, float, str]],
    mass_props: dict[str, float],
    vehicle: LaunchVehicle,
    payload_mass_kg: float,
    max_deploy_span_m: float,
) -> dict[str, Any]:
    cg_x, cg_y = mass_props["cg_x"], mass_props["cg_y"]
    max_g = vehicle.max_axial_g
    grid_mass = [[0.0] * GRID_COLS for _ in range(GRID_ROWS)]
    grid_power = [[0.0] * GRID_COLS for _ in range(GRID_ROWS)]
    sigma = 8.0
    for nx, ny, m, p, _ in parts:
        if m <= 0 and p <= 0:
            continue
        ci = min(GRID_COLS - 1, max(0, int(nx * (GRID_COLS - 1))))
        ri = min(GRID_ROWS - 1, max(0, int(ny * (GRID_ROWS - 1))))
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cx = c / (GRID_COLS - 1)
                cy = r / (GRID_ROWS - 1)
                d2 = (cx - nx) ** 2 + (cy - ny) ** 2
                w = math.exp(-d2 / (2 * sigma**2))
                grid_mass[r][c] += m * w
                grid_power[r][c] += p * w

    total_m = max(payload_mass_kg, 1.0)
    span = max(max_deploy_span_m, 0.5)
    first_bending_hz = max(8.0, 120.0 / span)
    excitation_bands = [12.0, 25.0, 42.0, 85.0, 120.0]

    stress: list[list[float]] = []
    power_norm: list[list[float]] = []
    max_stress = 1e-6
    max_pwr = 1e-6
    for r in range(GRID_ROWS):
        row_s, row_p = [], []
        cy = r / (GRID_ROWS - 1)
        for c in range(GRID_COLS):
            cx = c / (GRID_COLS - 1)
            local_mass = grid_mass[r][c]
            quasi = (max_g * G0 * local_mass / total_m) * 0.42
            arm = math.hypot(cx - cg_x, cy - cg_y)
            bending = max_g * 0.15 * arm * (payload_mass_kg / total_m) * 2.8
            vibe_coupling = 0.0
            for f in excitation_bands:
                vibe_coupling += 0.08 / (1.0 + 40.0 * (first_bending_hz - f) ** 2)
            acoustic = vehicle.fairing_acoustic_db / 200.0 * (0.3 + grid_mass[r][c] / total_m)
            shock = vehicle.shock_peak_g * 1e-6 * (1.0 + arm)
            thermal_grad = 0.12 * (1.0 - cy) * (payload_mass_kg / total_m)
            s_mpa = quasi + bending + vibe_coupling + acoustic + shock + thermal_grad
            row_s.append(s_mpa)
            row_p.append(grid_power[r][c])
            max_stress = max(max_stress, s_mpa)
            max_pwr = max(max_pwr, grid_power[r][c])
        stress.append(row_s)
        power_norm.append(row_p)

    hotspots: list[dict[str, Any]] = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            hotspots.append(
                {
                    "col": c,
                    "row": r,
                    "x": c / (GRID_COLS - 1),
                    "y": r / (GRID_ROWS - 1),
                    "stress_mpa": round(stress[r][c], 3),
                    "power_w": round(power_norm[r][c], 2),
                    "stress_norm": stress[r][c] / max_stress,
                    "power_norm": power_norm[r][c] / max_pwr if max_pwr > 0 else 0,
                }
            )
    hotspots.sort(key=lambda h: h["stress_mpa"], reverse=True)
    power_hotspots = sorted(hotspots, key=lambda h: h["power_w"], reverse=True)[:8]

    return {
        "cols": GRID_COLS,
        "rows": GRID_ROWS,
        "stress_mpa": stress,
        "power_w": power_norm,
        "max_stress_mpa": round(max_stress, 3),
        "max_power_w": round(max_pwr, 2),
        "cg": {"x": cg_x, "y": cg_y},
        "first_bending_hz": round(first_bending_hz, 1),
        "hotspots": hotspots[:12],
        "power_hotspots": power_hotspots,
    }


def compute_launch_compatibility(
    *,
    vehicle_id: str,
    orbit: str = "leo",
    profile: dict[str, Any] | None = None,
    annotations: list[Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {}
    annotations = annotations or []
    vehicle = VEHICLES.get(vehicle_id)
    if not vehicle:
        raise ValueError(f"unknown launch vehicle: {vehicle_id}")

    orbit_l = orbit.lower()
    dv_required = {"leo": DV_LEO, "gto": DV_GTO, "sso": DV_SSO}.get(orbit_l, DV_LEO)
    capacity = orbit_capacity_kg(vehicle, orbit_l)
    payload_mass, mass_source = _payload_mass_kg(profile, annotations)
    _, _, _, _, parts = _normalize_frame(annotations)
    mass_props = _mass_properties(parts)

    fairing_d = _num(profile, "fairing_diameter_m") or 2.5
    deploy_span = _num(profile, "deployable_span_m") or fairing_d * 0.85
    altitude_km = _num(profile, "orbit_altitude_km") or 550.0

    checks: list[CheckItem] = []
    category_scores: dict[str, float] = {}

    # --- 1. Mass, orbit, performance ---
    mass_margin = (capacity - payload_mass) / capacity if capacity > 0 else -1
    mass_status: CheckStatus = "pass" if mass_margin >= 0.12 else ("warn" if mass_margin >= 0 else "fail")
    checks.append(
        CheckItem(
            id="mass_capacity",
            category="mass_orbit",
            title="Payload mass vs vehicle capacity",
            status=mass_status,
            value=f"{payload_mass:.1f} kg",
            limit=f"{capacity:.0f} kg ({orbit_l.upper()})",
            detail=f"Mass from {mass_source}. Margin {mass_margin * 100:.1f}%.",
        )
    )

    dv_vehicle = _rocket_delta_v(vehicle)
    dv_status: CheckStatus = "pass" if dv_vehicle >= dv_required * 0.98 else "warn"
    checks.append(
        CheckItem(
            id="rocket_equation",
            category="mass_orbit",
            title="Rocket equation (vehicle Δv budget)",
            status=dv_status,
            value=f"{dv_vehicle:.0f} m/s",
            limit=f"{dv_required:.0f} m/s required",
            detail=(
                f"Δv ≈ Isp·g₀·ln(m₀/mf) with Isp={vehicle.isp_vac_s:.0f} s; "
                "payload capacity already embeds mission Δv."
            ),
        )
    )

    cg_off = mass_props["lateral_offset_mm"]
    cg_status: CheckStatus = "pass" if cg_off < 25 else ("warn" if cg_off < 80 else "fail")
    checks.append(
        CheckItem(
            id="center_of_gravity",
            category="mass_orbit",
            title="Center of gravity offset",
            status=cg_status,
            value=f"{cg_off:.1f} mm equiv.",
            limit="< 25 mm nominal",
            detail=f"CG at ({mass_props['cg_x']:.3f}, {mass_props['cg_y']:.3f}) normalized frame.",
        )
    )

    moi_ratio = mass_props["moi_pitch"] / max(mass_props["moi_yaw"], 1e-6)
    moi_status: CheckStatus = "pass" if 0.25 < moi_ratio < 4.0 else "warn"
    checks.append(
        CheckItem(
            id="moments_of_inertia",
            category="mass_orbit",
            title="Moments of inertia (pitch/yaw)",
            status=moi_status,
            value=f"{moi_ratio:.2f} ratio",
            limit="0.25 – 4.0",
            detail="Extreme inertia asymmetry can induce guidance torque during ascent.",
        )
    )
    category_scores["mass_orbit"] = _category_score(
        [c for c in checks if c.category == "mass_orbit"]
    )

    # --- 2. Volumetric / envelope ---
    static_ok = deploy_span <= vehicle.static_envelope_diameter_m
    dynamic_ok = deploy_span <= vehicle.dynamic_envelope_diameter_m
    env_status: CheckStatus = "pass" if dynamic_ok else ("warn" if static_ok else "fail")
    checks.append(
        CheckItem(
            id="static_envelope",
            category="envelope",
            title="Static fairing envelope",
            status="pass" if static_ok else "fail",
            value=f"{deploy_span:.2f} m span",
            limit=f"{vehicle.static_envelope_diameter_m:.2f} m",
            detail="Max deployable span vs static fairing cylinder.",
        )
    )
    checks.append(
        CheckItem(
            id="dynamic_envelope",
            category="envelope",
            title="Dynamic envelope (deflection)",
            status=env_status,
            value=f"{deploy_span:.2f} m",
            limit=f"{vehicle.dynamic_envelope_diameter_m:.2f} m",
            detail="Accounts for fairing/payload flex under ascent bending and acoustic excitation.",
        )
    )
    height_ok = fairing_d <= vehicle.fairing_height_m * 0.85
    checks.append(
        CheckItem(
            id="fairing_height",
            category="envelope",
            title="Stack height / diameter",
            status="pass" if height_ok else "warn",
            value=f"{fairing_d:.2f} m dia.",
            limit=f"{vehicle.fairing_height_m:.1f} m fairing",
            detail="User fairing diameter vs vehicle fairing height envelope.",
        )
    )
    category_scores["envelope"] = _category_score([c for c in checks if c.category == "envelope"])

    # --- 3. Structural / dynamic loads ---
    axial_force_kn = payload_mass * vehicle.max_axial_g * G0 / 1000
    checks.append(
        CheckItem(
            id="quasi_static",
            category="loads",
            title="Quasi-static acceleration",
            status="pass" if vehicle.max_axial_g <= 7.5 else "warn",
            value=f"{vehicle.max_axial_g:.1f} g / {axial_force_kn:.1f} kN",
            limit="5–7 g typical peak",
            detail="Crushing load at max-Q and stage cutoff; used as FEA static baseline.",
        )
    )

    vibe_margin = vehicle.fairing_acoustic_db - 135.0
    vibe_status: CheckStatus = "pass" if vibe_margin < 5 else ("warn" if vibe_margin < 8 else "fail")
    checks.append(
        CheckItem(
            id="vibroacoustic",
            category="loads",
            title="Vibroacoustic fairing level",
            status=vibe_status,
            value=f"{vehicle.fairing_acoustic_db:.0f} dB",
            limit="< 140 dB fragile payload",
            detail="Pad reflection drives broadband excitation; verify isolator tuning vs first bending mode.",
        )
    )

    checks.append(
        CheckItem(
            id="shock",
            category="loads",
            title="Pyrotechnic shock (stage/fairing sep.)",
            status="warn" if vehicle.shock_peak_g > 1000 else "pass",
            value=f"{vehicle.shock_peak_g:.0f} g SRS peak",
            limit="isolate avionics > 500 Hz",
            detail="Fairing separation and stage drops inject high-frequency shock into the bus.",
        )
    )
    category_scores["loads"] = _category_score([c for c in checks if c.category == "loads"])

    # --- 4. Thermal / environment ---
    heat_flux = 0.35 * (altitude_km / 550.0) ** 0.5 * 12.0
    checks.append(
        CheckItem(
            id="aero_heating",
            category="thermal",
            title="Aerodynamic heating (radiation inward)",
            status="pass" if heat_flux < 18 else "warn",
            value=f"{heat_flux:.1f} kW/m² proxy",
            limit="< 18 kW/m² payload",
            detail="Scales with ascent altitude; thermal model verifies bus panel survival.",
        )
    )

    vent_rate = 650.0 * (1.0 - altitude_km / 900.0)
    vent_status: CheckStatus = "pass" if vent_rate <= vehicle.depressurization_max_pa_per_s else "fail"
    checks.append(
        CheckItem(
            id="depressurization",
            category="thermal",
            title="Fairing depressurization rate",
            status=vent_status,
            value=f"{vent_rate:.0f} Pa/s",
            limit=f"{vehicle.depressurization_max_pa_per_s:.0f} Pa/s max",
            detail="Fast vent can rupture sealed cavities; verify vent paths and port sizing.",
        )
    )
    category_scores["thermal"] = _category_score([c for c in checks if c.category == "thermal"])

    stress_field = _build_stress_field(parts, mass_props, vehicle, payload_mass, deploy_span)

    overall = (
        0.30 * category_scores.get("mass_orbit", 0)
        + 0.25 * category_scores.get("envelope", 0)
        + 0.30 * category_scores.get("loads", 0)
        + 0.15 * category_scores.get("thermal", 0)
    )
    overall = round(overall)
    if overall >= 85:
        status: OverallStatus = "nominal"
    elif overall >= 70:
        status = "review"
    elif overall >= 50:
        status = "caution"
    else:
        status = "fail"

    warnings = [
        {
            "level": "crit" if c.status == "fail" else ("warn" if c.status == "warn" else "info"),
            "text": f"{c.title}: {c.detail}",
            "check_id": c.id,
        }
        for c in checks
        if c.status != "pass"
    ]

    return {
        "vehicle_id": vehicle.id,
        "vehicle_name": vehicle.name,
        "orbit": orbit_l,
        "overall_score": overall,
        "overall_status": status,
        "payload_mass_kg": round(payload_mass, 2),
        "mass_source": mass_source,
        "capacity_kg": capacity,
        "mass_margin_pct": round(mass_margin * 100, 1),
        "mass_properties": {k: round(v, 4) if isinstance(v, float) else v for k, v in mass_props.items()},
        "category_scores": {k: round(v) for k, v in category_scores.items()},
        "checks": [
            {
                "id": c.id,
                "category": c.category,
                "title": c.title,
                "status": c.status,
                "value": c.value,
                "limit": c.limit,
                "detail": c.detail,
            }
            for c in checks
        ],
        "warnings": warnings,
        "stress_field": stress_field,
        "simulation": {
            "engine": "launch_integration_v1",
            "fea_mode": "lumped_mass_grid",
            "notes": "Stress map is a surrogate FEA from mass/CG, quasi-static g, bending arm, and acoustic coupling.",
        },
    }


def _category_score(items: list[CheckItem]) -> float:
    if not items:
        return 50.0
    pts = {"pass": 100.0, "warn": 65.0, "fail": 20.0}
    return sum(pts[i.status] for i in items) / len(items)
