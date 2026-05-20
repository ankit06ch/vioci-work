"""Modelica exporter (multi-domain system dynamics).

Emits a minimal Modelica model with components mapped to the appropriate
Modelica Standard Library kinds (``Modelica.Electrical.Analog.Basic.Resistor``,
``Modelica.Mechanics.Translational.Components.Mass``, etc.) and
``connect()`` statements derived from IR edges.
"""

from __future__ import annotations

from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity


_KIND_TO_MODEL = {
    "resistor": ("Modelica.Electrical.Analog.Basic.Resistor", "R"),
    "capacitor": ("Modelica.Electrical.Analog.Basic.Capacitor", "C"),
    "inductor": ("Modelica.Electrical.Analog.Basic.Inductor", "L"),
    "voltage_source": ("Modelica.Electrical.Analog.Sources.ConstantVoltage", "V"),
    "current_source": ("Modelica.Electrical.Analog.Sources.ConstantCurrent", "I"),
    "ground": ("Modelica.Electrical.Analog.Basic.Ground", None),
    "mass": ("Modelica.Mechanics.Translational.Components.Mass", "m"),
    "spring": ("Modelica.Mechanics.Translational.Components.Spring", "c"),
    "damper": ("Modelica.Mechanics.Translational.Components.Damper", "d"),
    "force": ("Modelica.Mechanics.Translational.Sources.Force", None),
}


class ModelicaExporter(Exporter):
    name = "modelica"
    default_extension = "mo"
    binary = False

    def export(self, diagram: Diagram, *, model_name: str | None = None, **options: Any) -> str:
        name = model_name or f"D_{diagram.id.replace('-', '_')}"
        out: list[str] = [f"model {name}"]

        # parameters
        for p in diagram.parameters:
            unit = p.default.unit if p.default else ""
            val = p.default.value if p.default else 0.0
            unit_clause = f'(unit="{unit}")' if unit else ""
            out.append(f"  parameter Real {p.name}{unit_clause} = {val:g};")

        # component declarations
        id_to_ref: dict[str, str] = {}
        counters: dict[str, int] = {}
        for n in diagram.nodes:
            mapping = _KIND_TO_MODEL.get(n.kind)
            if mapping is None:
                continue
            modelica_type, value_arg = mapping
            stub = "".join(ch for ch in n.kind if ch.isalpha()) or "c"
            counters[stub] = counters.get(stub, 0) + 1
            ref = f"{stub}{counters[stub]}"
            id_to_ref[n.id] = ref
            arg = ""
            if value_arg is not None:
                v = _value_of(n.properties.get("value"))
                if v is not None:
                    arg = f"({value_arg}={v:g})"
            out.append(f"  {modelica_type} {ref}{arg};")

        out.append("equation")
        for e in diagram.edges:
            if e.kind not in {"wire", "rigid_link", "signal"}:
                continue
            src = id_to_ref.get(e.source)
            dst = id_to_ref.get(e.target)
            if src is None or dst is None:
                continue
            out.append(f"  connect({src}.p, {dst}.n);")

        out.append(f"end {name};")
        return "\n".join(out) + "\n"


def _value_of(v) -> float | None:
    if isinstance(v, Quantity):
        return float(v.value)
    if isinstance(v, (int, float)):
        return float(v)
    return None
