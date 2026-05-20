# Launch Physics Engine

Rigorous **analytical** launch integration for Vioci Schematic Explorer. This is an engineering analysis tool — not a certification artifact. Flight release still requires measured mass properties and qualification testing.

## Engine version

`launch_physics_v2` — traceable outputs with `engine_version` and `vehicle_data_rev` on every report.

## Data sources

| Source | Purpose |
|--------|---------|
| Bundled JSON (`schemagraph/launch_compat/vehicles/*.json`) | MPE quasi-static tables, PSD, SRS, modal floors, CG limits (from public Payload User Guides) |
| Mission profile | Mass, orbit, CG, MOI, vent geometry, modal frequencies |
| Part annotations | Per-component mass, L×W×H, material, power — required for structural FEA |
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
