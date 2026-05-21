# Launch readiness samples

Ready-to-use **SatelliteLaunchReadiness** fixtures for the Launch Physics Engine.

## Recommended for tests: `vioci_leo_observation_sat.json`

Small 6U-class LEO observation satellite (~142 kg, SSO 525 km). Fills every mission and component field so **15 of 16** physics checks run (`emc_rf` stays blocked until spectrum data exists).

| File | Use |
|------|-----|
| `vioci_leo_observation_sat.json` | Full manifest — copy into a project or load in pytest |
| `schema/launch/launch_mission.csv` | Single mission row (same data) |
| `schema/launch/launch_components.csv` | Four subsystem rows |
| `schema/launch/launch_check_catalog.csv` | Field → test_id reference |

### Use in the app

1. Upload or open a schematic project (any diagram image).
2. Either:
   - **File explorer:** select the project in the tree, then drop `vioci_leo_observation_sat.json` on the page, or
   - **Workspace:** open the **Launch** tab and drop the `.json` anywhere on that panel (or use **Import mission JSON**).

Alternatively, copy files into the project workspace: `schema/launch/launch_readiness.json` plus the three CSVs, then run the suite with vehicle **Falcon 9** and orbit **SSO**.

Or call the API:

```bash
# After copying files into the project workspace:
curl -H "Authorization: Bearer $TOKEN" \
  -X POST "http://127.0.0.1:8000/api/projects/YOUR_PROJECT_ID/launch-compat" \
  -H "Content-Type: application/json" \
  -d '{"vehicle_id":"f9","orbit":"sso","profile":{}}'
```

The server merges `launch_readiness.json` automatically when present.

### Use in pytest

```python
import json
from pathlib import Path
from schemagraph.launch_compat import LaunchPhysicsEngine
from schemagraph.launch_compat.schema.field_catalog import mission_to_profile, components_to_annotations

SAMPLE = Path("schemagraph/launch_compat/schema/samples/vioci_leo_observation_sat.json")
doc = json.loads(SAMPLE.read_text())
r = LaunchPhysicsEngine.run_suite(
    vehicle_id="f9",
    orbit="sso",
    profile=mission_to_profile(doc["mission"]),
    annotations=components_to_annotations(doc["components"]),
)
```

## Larger reference bus: `landsat_telemetry_bus.json`

847 kg Earth-observation bus with six components — same layout, useful for heavy-payload / envelope studies.
