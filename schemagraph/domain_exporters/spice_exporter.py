"""SPICE netlist exporter (ngspice-compatible).

Maps electrical-domain IR to a ``.cir`` netlist. Component kinds handled:
``resistor``, ``capacitor``, ``inductor``, ``voltage_source``,
``current_source``, ``diode``, ``ground``. Wires define net membership;
each connected component receives a node number (``0`` reserved for ground).
"""

from __future__ import annotations

from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity
from schemagraph.physics.units import normalize_quantity


_PREFIX_BY_KIND = {
    "resistor": "R",
    "capacitor": "C",
    "inductor": "L",
    "voltage_source": "V",
    "battery": "V",
    "current_source": "I",
    "diode": "D",
}

_UNIT_BY_KIND = {
    "resistor": "ohm",
    "capacitor": "farad",
    "inductor": "henry",
    "voltage_source": "volt",
    "battery": "volt",
    "current_source": "ampere",
}


class SPICEExporter(Exporter):
    name = "spice"
    default_extension = "cir"
    binary = False

    def export(self, diagram: Diagram, *, title: str | None = None, **options: Any) -> str:
        node_index = diagram.node_index()

        # Identify ground nodes
        ground_ids = {n.id for n in diagram.nodes if n.kind == "ground"}

        # Build a connectivity union-find over (node_id, port?) endpoints.
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        def endpoint_for(edge_endpoint: str) -> str:
            return edge_endpoint  # node id (or port id) — treated uniformly

        for n in diagram.nodes:
            parent[n.id] = n.id
        for e in diagram.edges:
            if e.kind == "wire":
                union(endpoint_for(e.source), endpoint_for(e.target))

        # Assign SPICE net numbers: 0 for any net containing a ground node.
        net_for_root: dict[str, int] = {}
        next_id = 1
        for root in {find(n.id) for n in diagram.nodes}:
            # Is any ground in this net?
            if any(find(g) == root for g in ground_ids):
                net_for_root[root] = 0
            else:
                net_for_root[root] = next_id
                next_id += 1

        def net_for(node_id: str) -> int:
            return net_for_root[find(node_id)]

        # Emit lines per component
        lines: list[str] = []
        lines.append(f"* schemagraph SPICE export :: {title or diagram.id}")
        counters: dict[str, int] = {}
        for n in diagram.nodes:
            prefix = _PREFIX_BY_KIND.get(n.kind)
            if prefix is None:
                continue
            counters[prefix] = counters.get(prefix, 0) + 1
            ref = f"{prefix}{counters[prefix]}"
            # find connected wires to enumerate net endpoints
            terminals = [e for e in diagram.edges if n.id in (e.source, e.target) and e.kind == "wire"]
            nets: list[int] = []
            for e in terminals:
                other = e.target if e.source == n.id else e.source
                nets.append(net_for(other))
            # most components are 2-terminal; ensure exactly two by padding with own net
            while len(nets) < 2:
                nets.append(net_for(n.id))
            nets = nets[:2]

            value = _emit_value(n.properties.get("value"), kind=n.kind)
            if value is None:
                # fall back to label or raw
                value = (n.label or "").strip() or "?"
            lines.append(f"{ref} {nets[0]} {nets[1]} {value}")

        # Optional .param block from Diagram.parameters
        for p in diagram.parameters:
            if p.default is not None:
                lines.append(f".param {p.name}={_quantity_for_spice(p.default)}")

        lines.append(".end")
        return "\n".join(lines) + "\n"


def _quantity_for_spice(q: Quantity) -> str:
    return f"{q.value:g}"


def _emit_value(value, *, kind: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, Quantity):
        target = _UNIT_BY_KIND.get(kind)
        if target and value.unit:
            converted = normalize_quantity(value, target)
            if converted is not None:
                return f"{converted.value:g}"
        return f"{value.value:g}"
    return str(value)
