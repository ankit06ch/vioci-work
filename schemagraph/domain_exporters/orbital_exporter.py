"""Orbital-mechanics exporter (poliastro-compatible JSON).

Maps diagrams that describe orbital bodies / orbits into a JSON document
compatible with poliastro/Orekit-style ingest: each body becomes a
named object with classical orbital elements when available, plus a
generic ``state`` block (position + velocity) when present.
"""

from __future__ import annotations

import json
from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity


_DEFAULT_UNIT = {
    "semi_major_axis": "km",
    "eccentricity": "dimensionless",
    "inclination": "deg",
    "raan": "deg",
    "arg_periapsis": "deg",
    "true_anomaly": "deg",
}


class OrbitalExporter(Exporter):
    name = "orbital"
    default_extension = "json"
    binary = False

    def export(self, diagram: Diagram, *, central_body: str = "Earth", **options: Any) -> str:
        bodies = []
        orbits = []
        for n in diagram.nodes:
            if n.kind in {"body", "satellite", "planet", "moon", "asteroid", "spacecraft"}:
                bodies.append(
                    {
                        "id": n.id,
                        "name": n.label or n.kind,
                        "kind": n.kind,
                        "mass": _quantity(n.properties.get("mass")),
                        "radius": _quantity(n.properties.get("radius")),
                    }
                )
            elif n.kind in {"orbit", "trajectory"}:
                orbits.append(
                    {
                        "id": n.id,
                        "central_body": central_body,
                        "elements": {
                            k: _quantity(n.properties.get(k), default_unit=_DEFAULT_UNIT.get(k))
                            for k in _DEFAULT_UNIT
                            if k in n.properties
                        },
                        "label": n.label,
                    }
                )

        doc = {
            "diagram_id": diagram.id,
            "central_body": central_body,
            "bodies": bodies,
            "orbits": orbits,
            "edges": [
                {"source": e.source, "target": e.target, "kind": e.kind, "label": e.label}
                for e in diagram.edges
            ],
        }
        return json.dumps(doc, indent=2, default=str)


def _quantity(v, default_unit: str | None = None) -> dict | None:
    if v is None:
        return None
    if isinstance(v, Quantity):
        return {"value": v.value, "unit": v.unit or default_unit, "raw": v.raw}
    if isinstance(v, (int, float)):
        return {"value": float(v), "unit": default_unit}
    return {"raw": str(v)}
