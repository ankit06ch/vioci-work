"""Export a Diagram to JSON-LD with a schemagraph @context.

The exported document is structured for downstream AI reasoning systems:
each node and edge is a JSON-LD subject with stable IRIs and typed
properties. Unit-aware Quantities are emitted with QUDT-friendly
``{value, unit}`` pairs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity


CONTEXT: dict[str, Any] = {
    "@version": 1.1,
    "sg": "https://schemagraph.dev/ns#",
    "id": "@id",
    "type": "@type",
    "label": "sg:label",
    "kind": "sg:kind",
    "domain": "sg:domain",
    "confidence": "sg:confidence",
    "properties": {"@id": "sg:properties", "@container": "@index"},
    "ports": {"@id": "sg:ports", "@container": "@set"},
    "nodes": {"@id": "sg:nodes", "@container": "@set"},
    "edges": {"@id": "sg:edges", "@container": "@set"},
    "constraints": {"@id": "sg:constraints", "@container": "@set"},
    "equations": {"@id": "sg:equations", "@container": "@set"},
    "datasets": {"@id": "sg:datasets", "@container": "@set"},
    "parameters": {"@id": "sg:parameters", "@container": "@set"},
    "source": "sg:source",
    "target": "sg:target",
    "directed": "sg:directed",
    "value": "sg:value",
    "unit": "sg:unit",
    "raw": "sg:raw",
}


class JSONLDExporter(Exporter):
    name = "jsonld"
    default_extension = "jsonld"
    binary = False

    def export(self, diagram: Diagram, *, indent: int = 2, **options: Any) -> str:
        doc = self._to_dict(diagram)
        return json.dumps(doc, indent=indent, default=str)

    def write(self, diagram: Diagram, path, **options: Any) -> Path:
        path = Path(path)
        path.write_text(self.export(diagram, **options), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    def _to_dict(self, diagram: Diagram) -> dict:
        return {
            "@context": CONTEXT,
            "@id": f"sg:diagram/{diagram.id}",
            "@type": "sg:Diagram",
            "schema_version": diagram.schema_version,
            "domain": diagram.domain,
            "source": diagram.source.model_dump(mode="json"),
            "nodes": [self._node(n) for n in diagram.nodes],
            "edges": [self._edge(e) for e in diagram.edges],
            "constraints": [self._constraint(c) for c in diagram.constraints],
            "equations": [self._equation(eq) for eq in diagram.equations],
            "datasets": [self._dataset(d) for d in diagram.datasets],
            "parameters": [self._parameter(p) for p in diagram.parameters],
            "metadata": diagram.metadata or {},
        }

    def _node(self, n) -> dict:
        return {
            "@id": f"sg:node/{n.id}",
            "@type": ["sg:Node", f"sg:kind/{n.kind}"],
            "kind": n.kind,
            "label": n.label,
            "domain": n.domain,
            "confidence": n.confidence,
            "tags": list(n.tags),
            "properties": {k: self._value(v) for k, v in (n.properties or {}).items()},
            "ports": [
                {
                    "@id": f"sg:port/{p.id}",
                    "@type": "sg:Port",
                    "role": p.role,
                    "direction": p.direction,
                    "position_px": p.position_px,
                }
                for p in n.ports
            ],
        }

    def _edge(self, e) -> dict:
        return {
            "@id": f"sg:edge/{e.id}",
            "@type": ["sg:Edge", f"sg:edgekind/{e.kind}"],
            "kind": e.kind,
            "label": e.label,
            "domain": e.domain,
            "directed": e.directed,
            "confidence": e.confidence,
            "source": f"sg:node/{e.source}",
            "target": f"sg:node/{e.target}",
            "properties": {k: self._value(v) for k, v in (e.properties or {}).items()},
        }

    def _constraint(self, c) -> dict:
        return {
            "@id": f"sg:constraint/{c.id}",
            "@type": ["sg:Constraint", f"sg:ctype/{c.kind}"],
            "kind": c.kind,
            "targets": [f"sg:ref/{t}" for t in c.targets],
            "expression": c.expression,
            "value": self._value(c.value) if c.value else None,
        }

    def _equation(self, eq) -> dict:
        return {
            "@id": f"sg:equation/{eq.id}",
            "@type": "sg:Equation",
            "raw": eq.raw,
            "sympy_repr": eq.sympy_repr,
            "variables": eq.variables,
        }

    def _dataset(self, d) -> dict:
        return {
            "@id": f"sg:dataset/{d.id}",
            "@type": "sg:Dataset",
            "name": d.name,
            "axes": d.axes,
            "series": [{"name": s.name, "values": s.values} for s in d.series],
        }

    def _parameter(self, p) -> dict:
        return {
            "@id": f"sg:parameter/{p.id}",
            "@type": "sg:Parameter",
            "name": p.name,
            "default": self._value(p.default) if p.default else None,
            "bounds": list(p.bounds) if p.bounds else None,
            "description": p.description,
            "targets": [f"sg:ref/{t}" for t in p.targets],
        }

    def _value(self, v: Any):
        if isinstance(v, Quantity):
            return {"@type": "sg:Quantity", "value": v.value, "unit": v.unit, "raw": v.raw}
        return v
