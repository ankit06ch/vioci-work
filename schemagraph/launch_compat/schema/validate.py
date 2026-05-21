"""Validate launch readiness documents against JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).parent / "satellite_launch_schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_document(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (ok, errors). Uses jsonschema if installed, else minimal checks."""
    errors: list[str] = []
    try:
        import jsonschema

        jsonschema.validate(doc, load_schema())
        return True, []
    except ImportError:
        pass
    except Exception as e:
        return False, [str(e)]

    if doc.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    mission = doc.get("mission") or {}
    for req in ("mass_kg", "orbit_altitude_km", "deployable_span_m", "fairing_diameter_m"):
        if mission.get(req) is None:
            errors.append(f"mission.{req} required")
    comps = doc.get("components") or []
    if not comps:
        errors.append("components must have at least one entry")
    for i, c in enumerate(comps):
        for req in ("component_id", "name", "mass_kg", "length_m", "width_m", "height_m", "material"):
            if not c.get(req):
                errors.append(f"components[{i}].{req} required for full suite")
    return len(errors) == 0, errors
