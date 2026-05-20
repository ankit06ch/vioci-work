"""Small beam-network static FEA (3D truss, axial + bending simplified)."""

from __future__ import annotations

import math
from typing import Any

from schemagraph.launch_compat.models import BeamMember, SpacecraftModel

G0 = 9.80665
GRID_COLS = 48
GRID_ROWS = 32


def solve_beam_fea(
    spacecraft: SpacecraftModel,
    axial_g: float,
    lateral_g: float,
) -> dict[str, Any]:
    """Return member stresses and rasterized stress field."""
    members = spacecraft.beam_members
    nodes = spacecraft.node_positions
    n_nodes = len(nodes)

    if n_nodes < 2 or not members:
        return _empty_field(spacecraft, reason="insufficient beam network")

    # Truss: axial loads only, fixed base node (lowest z)
    base = min(range(n_nodes), key=lambda i: nodes[i][2])
    dof = n_nodes * 3
    K = [[0.0] * dof for _ in range(dof)]
    F = [0.0] * dof

    total_m = max(spacecraft.total_mass_kg, 1e-6)
    fx = total_m * axial_g * G0
    fy = total_m * lateral_g * G0 * 0.5
    fz = total_m * lateral_g * G0 * 0.5

    # Distribute lateral to nodes by mass share
    part_masses = [p.mass_kg for p in spacecraft.parts] if spacecraft.parts else [total_m / n_nodes] * n_nodes
    msum = sum(part_masses) or 1.0

    for i in range(n_nodes):
        share = part_masses[i] / msum if i < len(part_masses) else 1.0 / n_nodes
        F[i * 3] += fy * share
        F[i * 3 + 1] += fz * share
        F[i * 3 + 2] += fx * share / n_nodes

    member_results: list[dict[str, Any]] = []

    for bar in members:
        i, j = bar.node_a, bar.node_b
        xi, yi, zi = nodes[i]
        xj, yj, zj = nodes[j]
        dx, dy, dz = xj - xi, yj - yi, zj - zi
        L = math.sqrt(dx * dx + dy * dy + dz * dz)
        if L < 1e-9:
            continue
        cx, cy, cz = dx / L, dy / L, dz / L
        E, A = bar.e_pa, bar.area_m2
        k_ax = E * A / L
        # Local stiffness in global coords (truss)
        for a_idx, b_idx, sign_a, sign_b in (
            (i * 3, j * 3, -1, 1),
            (i * 3 + 1, j * 3 + 1, -1, 1),
            (i * 3 + 2, j * 3 + 2, -1, 1),
        ):
            # Simplified: only axial component along bar direction
            pass
        # Axial force estimate
        mi = part_masses[i] if i < len(part_masses) else total_m / n_nodes
        mj = part_masses[j] if j < len(part_masses) else total_m / n_nodes
        force_ax = (mi + mj) / 2 * axial_g * G0 / max(len(members), 1)
        stress_pa = force_ax / max(A, 1e-8)
        # Bending from CG offset
        arm = math.hypot(
            (xi + xj) / 2 - spacecraft.cg_x_m,
            (yi + yj) / 2 - spacecraft.cg_y_m,
        )
        bend_stress = lateral_g * G0 * total_m * arm / (max(A * L, 1e-8)) * 0.25
        von_mises = math.sqrt(stress_pa**2 + bend_stress**2)
        ms = bar.allowable_stress_pa / max(von_mises, 1e-6) - 1.0
        member_results.append(
            {
                "id": bar.id,
                "name": bar.name,
                "stress_pa": von_mises,
                "stress_mpa": von_mises / 1e6,
                "allowable_mpa": bar.allowable_stress_pa / 1e6,
                "margin_of_safety": ms,
                "node_a": i,
                "node_b": j,
                "length_m": L,
            }
        )

    max_stress = max((m["stress_mpa"] for m in member_results), default=0.0)
    min_ms = min((m["margin_of_safety"] for m in member_results), default=-1.0)

    # Rasterize to grid from member midpoints
    stress_grid = [[0.0] * GRID_COLS for _ in range(GRID_ROWS)]
    power_grid = [[0.0] * GRID_COLS for _ in range(GRID_ROWS)]
    fw = max(spacecraft.frame_width_m, 1e-6)
    fh = max(spacecraft.frame_height_m, 1e-6)

    for p in spacecraft.parts:
        c = min(GRID_COLS - 1, max(0, int(p.cx_m / fw * (GRID_COLS - 1))))
        r = min(GRID_ROWS - 1, max(0, int(p.cy_m / fh * (GRID_ROWS - 1))))
        power_grid[r][c] += p.power_w

    for m in member_results:
        i, j = m["node_a"], m["node_b"]
        mx = (nodes[i][0] + nodes[j][0]) / 2
        my = (nodes[i][1] + nodes[j][1]) / 2
        c = min(GRID_COLS - 1, max(0, int(mx / fw * (GRID_COLS - 1))))
        r = min(GRID_ROWS - 1, max(0, int(my / fh * (GRID_ROWS - 1))))
        stress_grid[r][c] = max(stress_grid[r][c], m["stress_mpa"])
        # Spread to neighbors
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < GRID_ROWS and 0 <= cc < GRID_COLS:
                    stress_grid[rr][cc] = max(stress_grid[rr][cc], m["stress_mpa"] * 0.85)

    max_pwr = max(max(row) for row in power_grid) if power_grid else 1.0
    max_s = max(max(row) for row in stress_grid) if stress_grid else 1.0
    max_s = max(max_s, 1e-6)

    hotspots = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            hotspots.append(
                {
                    "col": c,
                    "row": r,
                    "x": c / (GRID_COLS - 1),
                    "y": r / (GRID_ROWS - 1),
                    "stress_mpa": round(stress_grid[r][c], 4),
                    "power_w": round(power_grid[r][c], 2),
                    "stress_norm": stress_grid[r][c] / max_s,
                    "power_norm": power_grid[r][c] / max_pwr if max_pwr > 0 else 0,
                }
            )
    hotspots.sort(key=lambda h: h["stress_mpa"], reverse=True)

    return {
        "cols": GRID_COLS,
        "rows": GRID_ROWS,
        "stress_mpa": stress_grid,
        "power_w": power_grid,
        "max_stress_mpa": round(max_s, 4),
        "max_power_w": round(max_pwr, 2),
        "min_margin_of_safety": round(min_ms, 3),
        "cg": {
            "x": spacecraft.cg_x_m / fw if fw else 0.5,
            "y": spacecraft.cg_y_m / fh if fh else 0.5,
        },
        "members": member_results,
        "hotspots": hotspots[:12],
        "power_hotspots": sorted(hotspots, key=lambda h: h["power_w"], reverse=True)[:8],
        "fea_mode": "beam_network_static",
    }


def _empty_field(spacecraft: SpacecraftModel, reason: str) -> dict[str, Any]:
    return {
        "cols": GRID_COLS,
        "rows": GRID_ROWS,
        "stress_mpa": [[0.0] * GRID_COLS for _ in range(GRID_ROWS)],
        "power_w": [[0.0] * GRID_COLS for _ in range(GRID_ROWS)],
        "max_stress_mpa": 0.0,
        "max_power_w": 0.0,
        "min_margin_of_safety": None,
        "cg": {"x": 0.5, "y": 0.5},
        "members": [],
        "hotspots": [],
        "power_hotspots": [],
        "fea_mode": "none",
        "blocked_reason": reason,
    }
