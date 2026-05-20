"""Assemble SpacecraftModel from profile, annotations, and diagram."""

from __future__ import annotations

import math
from typing import Any

from schemagraph.launch_compat.models import BeamMember, PartMassProperties, SpacecraftModel, num
from schemagraph.launch_compat.structural.material_db import lookup_material

G0 = 9.80665
STRUCTURAL_KINDS = frozenset(
    {"structure", "frame", "panel", "bus", "truss", "beam", "link", "support", "wall"}
)


def _ann_field(a: Any, key: str, default=None):
    if isinstance(a, dict):
        return a.get(key, default)
    return getattr(a, key, default)


def _part_mass(a: Any) -> float | None:
    m = _ann_field(a, "mass_kg")
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return None
    return float(m)


def _has_structural_data(a: Any) -> bool:
    m = _part_mass(a)
    if m is None or m <= 0:
        return False
    l = _ann_field(a, "length_m")
    w = _ann_field(a, "width_m")
    h = _ann_field(a, "height_m")
    return all(x is not None and float(x) > 0 for x in (l, w, h))


def assemble_spacecraft(
    profile: dict[str, Any],
    annotations: list[Any],
    diagram: dict[str, Any] | None = None,
) -> SpacecraftModel:
    pm = num(profile, "mass_kg")
    parts: list[PartMassProperties] = []
    masses_from_parts: list[float] = []
    xs, ys, zs = [], [], []

    for a in annotations:
        bbox = _ann_field(a, "bbox")
        if not bbox:
            continue
        if isinstance(bbox, dict):
            bx, by, bw, bh = float(bbox["x"]), float(bbox["y"]), float(bbox["w"]), float(bbox["h"])
        else:
            bx, by, bw, bh = float(bbox.x), float(bbox.y), float(bbox.w), float(bbox.h)
        m = _part_mass(a)
        if m is None:
            continue
        l = float(_ann_field(a, "length_m") or bw * 0.001)
        w = float(_ann_field(a, "width_m") or bh * 0.001)
        h = float(_ann_field(a, "height_m") or min(l, w) * 0.5)
        cx = bx + bw / 2
        cy = by + bh / 2
        cz = h / 2
        mat = _ann_field(a, "material")
        pwr = float(_ann_field(a, "power_w") or 0)
        pid = str(_ann_field(a, "id", "part"))
        pname = str(_ann_field(a, "name", pid))
        parts.append(
            PartMassProperties(
                id=pid,
                name=pname,
                mass_kg=m,
                cx_m=cx * 0.001,
                cy_m=cy * 0.001,
                cz_m=cz,
                length_m=l,
                width_m=w,
                height_m=h,
                power_w=pwr,
                material=str(mat) if mat else None,
                has_structural_data=_has_structural_data(a),
            )
        )
        masses_from_parts.append(m)
        xs.extend([cx * 0.001, (cx + bw) * 0.001])
        ys.extend([cy * 0.001, (cy + bh) * 0.001])
        zs.extend([0, h])

    if pm and pm > 0:
        total_mass, mass_source = pm, "mission profile"
    elif masses_from_parts:
        total_mass, mass_source = sum(masses_from_parts), "annotated parts"
    else:
        total_mass, mass_source = 0.0, "missing"

    # CG from profile override (mm above SIP) or computed
    cg_x = (num(profile, "cg_x_mm") or 0) / 1000.0
    cg_y = (num(profile, "cg_y_mm") or 0) / 1000.0
    cg_z = (num(profile, "cg_z_mm") or 0) / 1000.0
    moi_measured = False
    ixx = num(profile, "moi_ixx_kgm2")
    iyy = num(profile, "moi_iyy_kgm2")
    izz = num(profile, "moi_izz_kgm2")

    if parts and total_mass > 0 and cg_x == 0 and cg_y == 0 and cg_z == 0:
        cg_x = sum(p.mass_kg * p.cx_m for p in parts) / total_mass
        cg_y = sum(p.mass_kg * p.cy_m for p in parts) / total_mass
        cg_z = sum(p.mass_kg * p.cz_m for p in parts) / total_mass

    if ixx is not None and iyy is not None and izz is not None:
        moi_ixx, moi_iyy, moi_izz = ixx, iyy, izz
        moi_measured = True
    elif parts and total_mass > 0:
        moi_ixx = sum(p.mass_kg * (p.cy_m**2 + p.cz_m**2) for p in parts)
        moi_iyy = sum(p.mass_kg * (p.cx_m**2 + p.cz_m**2) for p in parts)
        moi_izz = sum(p.mass_kg * (p.cx_m**2 + p.cy_m**2) for p in parts)
    else:
        moi_ixx = moi_iyy = moi_izz = 0.0

    xmin, xmax = (min(xs), max(xs)) if xs else (0, 1)
    ymin, ymax = (min(ys), max(ys)) if ys else (0, 1)
    zmax = max(zs) if zs else 1.0
    frame_w = max(xmax - xmin, 0.5)
    frame_h = max(ymax - ymin, 0.5)
    frame_d = max(zmax, 0.3)

    deploy = num(profile, "deployable_span_m") or max(frame_w, frame_h)
    fairing_d = num(profile, "fairing_diameter_m") or max(frame_w, frame_h) * 1.1

    missing_struct = [p.name for p in parts if not p.has_structural_data]

    node_positions = [(p.cx_m, p.cy_m, p.cz_m) for p in parts]
    beam_members = _build_beam_network(parts, diagram)

    return SpacecraftModel(
        total_mass_kg=total_mass,
        mass_source=mass_source,
        parts=parts,
        cg_x_m=cg_x,
        cg_y_m=cg_y,
        cg_z_m=cg_z,
        moi_ixx=moi_ixx,
        moi_iyy=moi_iyy,
        moi_izz=moi_izz,
        moi_from_measured=moi_measured,
        frame_width_m=frame_w,
        frame_height_m=frame_h,
        frame_depth_m=frame_d,
        deployable_span_m=deploy,
        fairing_diameter_m=fairing_d,
        beam_members=beam_members,
        node_positions=node_positions,
        missing_structural_parts=missing_struct,
    )


def _build_beam_network(parts: list[PartMassProperties], diagram: dict[str, Any] | None) -> list[BeamMember]:
    if len(parts) < 2:
        return []
    members: list[BeamMember] = []
    n = len(parts)
    connected: set[tuple[int, int]] = set()

    if diagram:
        node_to_idx = {}
        for i, p in enumerate(parts):
            if p.id:
                node_to_idx[p.id] = i
        for e in diagram.get("edges") or []:
            src, tgt = e.get("source"), e.get("target")
            if src in node_to_idx and tgt in node_to_idx:
                i, j = node_to_idx[src], node_to_idx[tgt]
                if i != j:
                    connected.add((min(i, j), max(i, j)))

    # Connect nearest neighbors for structure graph
    for i in range(n):
        dists = []
        for j in range(n):
            if i == j:
                continue
            pi, pj = parts[i], parts[j]
            d = math.sqrt((pi.cx_m - pj.cx_m) ** 2 + (pi.cy_m - pj.cy_m) ** 2 + (pi.cz_m - pj.cz_m) ** 2)
            dists.append((d, j))
        dists.sort()
        for _, j in dists[:2]:
            connected.add((min(i, j), max(i, j)))

    for idx, (i, j) in enumerate(connected):
        pi, pj = parts[i], parts[j]
        L = math.sqrt((pi.cx_m - pj.cx_m) ** 2 + (pi.cy_m - pj.cy_m) ** 2 + (pi.cz_m - pj.cz_m) ** 2)
        if L < 1e-6:
            continue
        mat = lookup_material(pi.material or pj.material)
        area = max(pi.width_m * pi.height_m, 1e-4)
        members.append(
            BeamMember(
                id=f"bar_{idx}",
                node_a=i,
                node_b=j,
                length_m=L,
                area_m2=area,
                e_pa=mat.e_pa,
                allowable_stress_pa=mat.allowable_stress_pa,
                name=f"{pi.name}—{pj.name}",
            )
        )
    return members
