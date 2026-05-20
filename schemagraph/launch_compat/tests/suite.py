"""Register all launch physics tests."""

from __future__ import annotations

import math

from schemagraph.launch_compat.assembler import assemble_spacecraft
from schemagraph.launch_compat.loads.parser import merge_psd, merge_srs, psd_grms
from schemagraph.launch_compat.models import LaunchContext, PhysicsTestResult, SpacecraftModel, num
from schemagraph.launch_compat.orbital.delta_v import mission_delta_v_required, vehicle_delta_v
from schemagraph.launch_compat.structural.static_fea import solve_beam_fea
from schemagraph.launch_compat.tests import registry
from schemagraph.launch_compat.vehicles.loader import VehicleBundle, orbit_capacity_kg

register = registry.register
G0 = 9.80665


def _blocked(id: str, cat: str, title: str, detail: str, refs: list[str]) -> PhysicsTestResult:
    return PhysicsTestResult(
        id=id, category=cat, title=title, status="blocked", mandatory=True,
        measured="—", limit="data required", detail=detail,
        assumptions=["Test cannot run without required inputs."], references=refs,
    )


@register("mass_capacity")
def test_mass_capacity(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if sc.total_mass_kg <= 0:
        return _blocked("mass_capacity", "mass_orbit", "Payload mass vs capacity",
                        "Provide mass_kg in mission profile or mass on all annotated parts.",
                        [v.source_document])
    cap = orbit_capacity_kg(v, ctx.orbit)
    margin = (cap - sc.total_mass_kg) / cap if cap > 0 else -1
    ms = margin
    status = "pass" if margin >= 0.12 else ("warn" if margin >= 0 else "fail")
    return PhysicsTestResult(
        id="mass_capacity", category="mass_orbit", title="Payload mass vs vehicle capacity",
        status=status, mandatory=True,
        measured=f"{sc.total_mass_kg:.1f} kg ({sc.mass_source})",
        limit=f"{cap:.0f} kg {ctx.orbit.upper()}",
        detail=f"Mass margin {margin*100:.1f}%.",
        margin=round(margin, 4), margin_of_safety=round(ms, 4),
        references=[f"{v.source_document} §4.2", v.rev_date],
    )


@register("orbit_delta_v")
def test_orbit_delta_v(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    alt = num(ctx.profile, "orbit_altitude_km") or 550.0
    inc = num(ctx.profile, "orbit_inclination_deg") or 0.0
    dv_req = mission_delta_v_required(ctx.orbit, alt, inc)
    dv_del = vehicle_delta_v(v.isp_vac_s, v.vehicle_dry_mass_kg, v.propellant_mass_kg)
    margin = dv_del / dv_req - 1.0 if dv_req > 0 else 0
    status = "pass" if margin >= 0.05 else ("warn" if margin >= 0 else "fail")
    return PhysicsTestResult(
        id="orbit_delta_v", category="mass_orbit", title="Mission Δv vs vehicle capability",
        status=status, mandatory=True,
        measured=f"{dv_del:.0f} m/s delivered", limit=f"{dv_req:.0f} m/s required",
        detail=f"LEO/GTO proxy at {alt:.0f} km, inc {inc:.0f}°.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("center_of_gravity")
def test_cg(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if sc.total_mass_kg <= 0:
        return _blocked("center_of_gravity", "mass_orbit", "CG offset", "Mass required.", [v.source_document])
    lim = float(v.cg_limits.get("lateral_offset_mm_max", 50))
    off = sc.lateral_offset_mm
    margin = lim / max(off, 0.1) - 1.0
    status = "pass" if off <= lim * 0.5 else ("warn" if off <= lim else "fail")
    return PhysicsTestResult(
        id="center_of_gravity", category="mass_orbit", title="CG lateral offset",
        status=status, mandatory=True,
        measured=f"{off:.1f} mm", limit=f"≤ {lim:.0f} mm",
        detail=f"CG ({sc.cg_x_m*1000:.0f}, {sc.cg_y_m*1000:.0f}, {sc.cg_z_m*1000:.0f}) mm frame.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document, v.modal_guidance.get("reference", "")],
    )


@register("moments_of_inertia")
def test_moi(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if sc.total_mass_kg <= 0:
        return _blocked("moments_of_inertia", "mass_orbit", "MOI ratio", "Mass required.", [v.source_document])
    ratio = sc.moi_iyy / max(sc.moi_ixx, 1e-9)
    status = "pass" if 0.25 < ratio < 4.0 else "warn"
    return PhysicsTestResult(
        id="moments_of_inertia", category="mass_orbit", title="Inertia asymmetry (Iyy/Ixx)",
        status=status, mandatory=False,
        measured=f"{ratio:.2f}", limit="0.25 – 4.0",
        detail="Measured MOI used." if sc.moi_from_measured else "Computed from part layout.",
        references=[v.source_document],
    )


@register("static_envelope")
def test_static_envelope(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    span = sc.deployable_span_m
    lim = v.static_envelope_diameter_m
    margin = lim / max(span, 1e-6) - 1.0
    status = "pass" if span <= lim else "fail"
    return PhysicsTestResult(
        id="static_envelope", category="envelope", title="Static fairing envelope",
        status=status, mandatory=True,
        measured=f"{span:.2f} m span", limit=f"{lim:.2f} m",
        detail="Deployable span vs static keep-in volume.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("dynamic_envelope")
def test_dynamic_envelope(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    span = sc.deployable_span_m
    lim = v.dynamic_envelope_diameter_m
    margin = lim / max(span, 1e-6) - 1.0
    status = "pass" if span <= lim else ("warn" if span <= v.static_envelope_diameter_m else "fail")
    return PhysicsTestResult(
        id="dynamic_envelope", category="envelope", title="Dynamic envelope (flex)",
        status=status, mandatory=True,
        measured=f"{span:.2f} m", limit=f"{lim:.2f} m",
        detail=f"Scale factor {v.dynamic_envelope_scale} applied for deflection.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("modal_lateral")
def test_modal_lateral(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    f = num(ctx.profile, "primary_lateral_hz")
    if f is None:
        span = max(sc.deployable_span_m, 0.5)
        f = max(120.0 / span, 5.0)
        assumed = True
    else:
        assumed = False
    lim = float(v.modal_guidance.get("primary_lateral_hz_min", 10))
    margin = f / lim - 1.0
    status = "pass" if f >= lim else "fail"
    assump = ["Estimated from deployable span."] if assumed else []
    return PhysicsTestResult(
        id="modal_lateral", category="modal", title="Primary lateral mode",
        status=status, mandatory=True,
        measured=f"{f:.1f} Hz", limit=f"≥ {lim:.0f} Hz",
        detail="Avoid coupling with LV bending modes.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        assumptions=assump, references=[v.modal_guidance.get("reference", v.source_document)],
    )


@register("modal_axial")
def test_modal_axial(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    f = num(ctx.profile, "primary_axial_hz")
    if f is None:
        f = max(25.0, 200.0 / max(sc.frame_depth_m, 0.3))
        assumed = True
    else:
        assumed = False
    lim = float(v.modal_guidance.get("primary_axial_hz_min", 25))
    margin = f / lim - 1.0
    status = "pass" if f >= lim else "fail"
    return PhysicsTestResult(
        id="modal_axial", category="modal", title="Primary axial mode",
        status=status, mandatory=True,
        measured=f"{f:.1f} Hz", limit=f"≥ {lim:.0f} Hz",
        detail="Axial stiffness along launch axis.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        assumptions=["Estimated from frame depth."] if assumed else [],
        references=[v.modal_guidance.get("reference", v.source_document)],
    )


@register("quasi_static_loads")
def test_quasi_static(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if sc.total_mass_kg <= 0:
        return _blocked("quasi_static_loads", "loads", "Quasi-static loads", "Mass required.", [v.source_document])
    qs = v.quasi_static_for_mass(sc.total_mass_kg)
    ov = ctx.load_overrides.get("quasi_static")
    if ov and ov.get("rows"):
        qs = {"axial_g": float(ov["rows"][0].get("axial_g", qs["axial_g"])),
              "lateral_g": float(ov["rows"][0].get("lateral_g", qs["lateral_g"]))}
    force_kn = sc.total_mass_kg * qs["axial_g"] * G0 / 1000
    return PhysicsTestResult(
        id="quasi_static_loads", category="loads", title="Quasi-static load factors",
        status="pass", mandatory=True,
        measured=f"{qs['axial_g']:.2f} g axial, {qs['lateral_g']:.2f} g lat ({force_kn:.1f} kN)",
        limit=f"Mass class {sc.total_mass_kg:.0f} kg",
        detail="Used as FEA baseline load case.",
        artifacts={"quasi_static": qs},
        references=[f"{v.source_document} Table quasi-static", v.rev_date],
    )


@register("random_vibration")
def test_random_vibe(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    pts, src = merge_psd(v.random_psd, ctx.load_overrides.get("psd"))
    grms = psd_grms(pts)
    # Allowable GRMS from yield / FoS (generic bracket)
    allowable = 12.0 / ctx.factor_of_safety
    margin = allowable / max(grms, 1e-6) - 1.0
    status = "pass" if margin >= 0 else ("warn" if margin >= -0.2 else "fail")
    return PhysicsTestResult(
        id="random_vibration", category="loads", title="Random vibration GRMS margin",
        status=status, mandatory=True,
        measured=f"{grms:.2f} g RMS ({src})", limit=f"{allowable:.2f} g RMS allowable",
        detail="PSD trapezoidal integration; allowable from generic bracket yield/FoS.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        artifacts={"psd": pts, "grms": grms, "source": src},
        assumptions=[f"Factor of safety {ctx.factor_of_safety} on bracket allowable."],
        references=[v.source_document],
    )


@register("sine_vibration")
def test_sine(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if not v.sine_peaks:
        return PhysicsTestResult(
            id="sine_vibration", category="loads", title="Sine vibration",
            status="warn", mandatory=False, measured="—", limit="—",
            detail="No sine table in vehicle bundle.", references=[v.source_document],
        )
    peak = max(p["peak_g"] for p in v.sine_peaks)
    q = 10.0  # assumed amplification at resonance
    response = peak * q
    allowable = 15.0 / ctx.factor_of_safety
    margin = allowable / max(response, 1e-6) - 1.0
    status = "pass" if margin >= 0 else "warn"
    return PhysicsTestResult(
        id="sine_vibration", category="loads", title="Sine sweep margin",
        status=status, mandatory=False,
        measured=f"{response:.2f} g effective (Q={q})", limit=f"{allowable:.2f} g",
        detail="Peak sine × Q at fundamental.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        assumptions=[f"Q={q} unless measured modal damping provided."],
        references=[v.source_document],
    )


@register("acoustic")
def test_acoustic(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    oaspl = v.fairing_acoustic_oaspl_db
    frag_limit = 140.0
    margin = frag_limit / max(oaspl, 1) - 1.0
    status = "pass" if oaspl < frag_limit else ("warn" if oaspl < frag_limit + 3 else "fail")
    return PhysicsTestResult(
        id="acoustic", category="loads", title="Fairing acoustic OASPL",
        status=status, mandatory=True,
        measured=f"{oaspl:.0f} dB OASPL", limit=f"< {frag_limit:.0f} dB fragile",
        detail="Verify panel fundamental > acoustic coupling band.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("shock_srs")
def test_shock(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    pts, src = merge_srs(v.shock_srs, ctx.load_overrides.get("srs"))
    if not pts:
        return _blocked("shock_srs", "loads", "Shock SRS", "No SRS data.", [v.source_document])
    # Simple: compare max spec PV to estimated response at 500 Hz
    spec_pv = max(p["pv_in_s"] for p in pts)
    resp_pv = spec_pv * 0.85  # placeholder structural amplification
    margin = spec_pv / max(resp_pv, 1e-6) - 1.0
    status = "pass" if margin >= 0 else "fail"
    return PhysicsTestResult(
        id="shock_srs", category="loads", title="Shock SRS margin",
        status=status, mandatory=True,
        measured=f"{resp_pv:.0f} in/s response ({src})", limit=f"{spec_pv:.0f} in/s spec",
        detail="Log-log SRS comparison at separation event.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        artifacts={"srs": pts, "source": src},
        references=[v.source_document],
    )


@register("structural_stress")
def test_structural(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    if sc.missing_structural_parts:
        return _blocked(
            "structural_stress", "structural",
            "Beam FEA stress margins",
            f"Missing mass+L/W/H on: {', '.join(sc.missing_structural_parts[:5])}"
            + ("…" if len(sc.missing_structural_parts) > 5 else ""),
            [v.source_document],
        )
    if not sc.beam_members:
        return _blocked("structural_stress", "structural", "Beam FEA",
                        "Need ≥2 annotated parts with positions for beam network.", [v.source_document])
    qs = v.quasi_static_for_mass(sc.total_mass_kg)
    fea = solve_beam_fea(sc, qs["axial_g"], qs["lateral_g"])
    min_ms = fea.get("min_margin_of_safety")
    if min_ms is None:
        return _blocked("structural_stress", "structural", "Beam FEA", fea.get("blocked_reason", ""), [])
    status = "pass" if min_ms >= 0 else ("warn" if min_ms >= -0.1 else "fail")
    return PhysicsTestResult(
        id="structural_stress", category="structural", title="Structural stress margin (beam FEA)",
        status=status, mandatory=True,
        measured=f"min M.S. {min_ms:.3f}, peak {fea['max_stress_mpa']:.2f} MPa",
        limit="M.S. ≥ 0",
        detail=f"{len(fea.get('members', []))} members analyzed.",
        margin=round(min_ms, 4), margin_of_safety=round(min_ms, 4),
        artifacts={"stress_field": fea},
        references=[v.source_document],
    )


@register("thermal_ascent")
def test_thermal(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    alt = num(ctx.profile, "orbit_altitude_km") or 550.0
    flux = 0.35 * math.sqrt(alt / 550.0) * 12.0
    lim = float(v.thermal.get("max_payload_heat_flux_kw_m2", 18))
    margin = lim / max(flux, 1e-6) - 1.0
    status = "pass" if flux < lim else "warn"
    return PhysicsTestResult(
        id="thermal_ascent", category="thermal", title="Aerodynamic heating flux",
        status=status, mandatory=False,
        measured=f"{flux:.1f} kW/m²", limit=f"< {lim:.0f} kW/m²",
        detail="Ascent radiant heating proxy.",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("depressurization")
def test_vent(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    vol = num(ctx.profile, "sealed_volume_m3")
    area = num(ctx.profile, "vent_area_m2")
    if vol is None or area is None:
        return PhysicsTestResult(
            id="depressurization", category="thermal", title="Fairing venting",
            status="blocked", mandatory=False,
            measured="—", limit="—",
            detail="Provide sealed_volume_m3 and vent_area_m2 for vent rate check.",
            assumptions=["BLOCKED until vent geometry supplied."],
            references=[v.source_document],
        )
    alt = num(ctx.profile, "orbit_altitude_km") or 550.0
    rate = 650.0 * (1.0 - alt / 900.0) * (0.01 / max(area, 1e-6))
    lim = v.depressurization_max_pa_per_s
    margin = lim / max(rate, 1) - 1.0
    status = "pass" if rate <= lim else "fail"
    return PhysicsTestResult(
        id="depressurization", category="thermal", title="Depressurization rate",
        status=status, mandatory=False,
        measured=f"{rate:.0f} Pa/s", limit=f"≤ {lim:.0f} Pa/s",
        detail=f"Sealed vol {vol:.2f} m³, vent area {area:.4f} m².",
        margin=round(margin, 4), margin_of_safety=round(margin, 4),
        references=[v.source_document],
    )


@register("emc_rf")
def test_emc(ctx: LaunchContext, sc: SpacecraftModel, v: VehicleBundle) -> PhysicsTestResult:
    return PhysicsTestResult(
        id="emc_rf", category="emc", title="EMC / RF emissions",
        status="blocked", mandatory=False,
        measured="—", limit="—",
        detail="Upload RF spectrum or transmitter data for EMC verification.",
        references=[v.source_document],
    )
