# AEGIS-LV Mission Assurance Engine

Rigorous **analytical** launch integration for Vioci Schematic Explorer. This is an engineering analysis tool — not a certification artifact. Flight release still requires measured mass properties and qualification testing.

## Engine version

`AEGIS-LV` — the user-facing mission assurance engine for launch compatibility.

`launch_physics_v2` — the traceable analytical core emitted as `engine_version`, with `vehicle_data_rev` on every report.

## Data sources

| Source | Purpose |
|--------|---------|
| Bundled JSON (`schemagraph/launch_compat/vehicles/*.json`) | MPE quasi-static tables, PSD, SRS, modal floors, CG limits (from public Payload User Guides) |
| Mission profile | Mass, orbit, CG, MOI, vent geometry, modal frequencies |
| Part annotations | Per-component mass, L×W×H, material, power — required for structural FEA |
| **Launch readiness schema** | `schemagraph/launch_compat/schema/satellite_launch_schema.json` — mission + components validated on parse; exported to CSV under `schema/launch/` |
| Uploaded load files | CSV/JSON PSD or SRS overrides mission-specific environments |

**Merge policy:** uploaded curves override bundled defaults per kind (`psd`, `srs`, `quasi_static`).

## Physics test suite

| ID | Category | Mandatory | Notes |
|----|----------|-----------|-------|
| `mass_capacity` | mass_orbit | yes | Payload vs vehicle capacity |
| `orbit_delta_v` | mass_orbit | yes | Mission Δv vs Tsiolkovsky vehicle budget |
| `center_of_gravity` | mass_orbit | yes | Lateral CG offset vs vehicle limit |
| `moments_of_inertia` | mass_orbit | no | Iyy/Ixx ratio |
| `static_envelope` | envelope | yes | Deployable span vs static fairing |
| `dynamic_envelope` | envelope | yes | Deflection-scaled envelope |
| `modal_lateral` | modal | yes | ≥ vehicle primary lateral Hz |
| `modal_axial` | modal | yes | ≥ vehicle primary axial Hz |
| `quasi_static_loads` | loads | yes | Mass-class QS factors |
| `random_vibration` | loads | yes | PSD → GRMS margin |
| `sine_vibration` | loads | no | Peak × Q margin |
| `acoustic` | loads | yes | OASPL vs fragile limit |
| `shock_srs` | loads | yes | SRS pseudo-velocity margin |
| `structural_stress` | structural | yes | Beam-network static FEA, M.S. ≥ 0 |
| `thermal_ascent` | thermal | no | Heating flux proxy |
| `depressurization` | thermal | no | Requires vent_area + sealed_volume |
| `emc_rf` | emc | no | BLOCKED until spectrum data |

## Verdict logic

- **NO-GO** if any mandatory test is `fail` or `blocked`
- **REVIEW** if mandatory failures absent but other failures exist
- **GO** otherwise

`blocked` means required inputs are missing — never scored as pass.

## Launch readiness schema (CSV on upload)

On schematic upload or parse, Vioci builds a **SatelliteLaunchReadiness** document (`schema/launch/launch_readiness.json`) and three CSVs:

| File | Contents |
|------|----------|
| `launch_mission.csv` | One row: mass, orbit, CG/MOI, venting, fairing, vehicle prefs |
| `launch_components.csv` | One row per annotated part: mass, L×W×H, material, bbox |
| `launch_check_catalog.csv` | Field → physics test mapping (which inputs unblock which checks) |

Schema: `schemagraph/launch_compat/schema/satellite_launch_schema.json`. Sample bus: `schema/samples/landsat_telemetry_bus.json`.

`check_readiness` on the manifest lists `tests_unblocked` vs missing mission/component fields so the Launch tab can show BLOCKED gates before running the suite.

- `GET /api/projects/launch-readiness/schema` — JSON Schema
- `GET /api/projects/{id}/launch-readiness` — project manifest
- `POST /api/projects/{id}/launch-readiness/rebuild` — refresh from diagram + annotations

## API

- `POST /api/projects/{id}/launch-compat` — full suite
- `POST /api/projects/{id}/launch-compat/tests/{test_id}` — single test
- `GET /api/projects/{id}/launch-compat/report` — last persisted report
- `POST /api/projects/{id}/launch-loads` — upload PSD/SRS CSV (multipart: `kind`, `file`)

## Assumptions (structural)

- Beam network: truss-like axial + bending proxy between annotated part centroids
- Materials: lookup from `structural/material_db.py` (aluminum, CFRP, etc.)
- Default factor of safety: 2.0 on bracket allowables for random vibe

## References

- SpaceX Falcon Payload User Guide (2025-05-09 representative tables)
- Electron / Vulcan / Ariane 6 / Starship: representative envelopes for integration studies
