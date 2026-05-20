"""Parametric overrides for downstream parameter sweeps.

A :class:`Parameter` declares a named user-overridable knob and a list of
``targets`` — property paths of the form ``"<node_id>.<property>"`` or
``"<edge_id>.<property>"`` — that the parameter drives. This module
applies a dict of name -> value (or Quantity) overrides to a Diagram,
returning a new Diagram with the resolved values substituted in.

Used for parameter sweeps, optimization, and what-if simulations under
arbitrary user-defined conditions.
"""

from __future__ import annotations

from typing import Any, Mapping

from schemagraph.ir.schema import Diagram, Edge, Node, Parameter, Quantity
from schemagraph.physics.units import coerce_quantity


def apply_parameters(
    diagram: Diagram, overrides: Mapping[str, Any]
) -> Diagram:
    """Return a new Diagram with the given parameter overrides applied.

    ``overrides`` maps parameter name -> new value (anything coercible to
    :class:`Quantity`, including raw strings like ``"22kΩ"`` or ``{"value":
    22000, "unit": "ohm"}``). Unknown names are ignored.
    """
    by_name = {p.name: p for p in diagram.parameters}
    if not by_name:
        return diagram

    new_nodes = [n.model_copy(deep=True) for n in diagram.nodes]
    new_edges = [e.model_copy(deep=True) for e in diagram.edges]
    node_idx = {n.id: i for i, n in enumerate(new_nodes)}
    edge_idx = {e.id: i for i, e in enumerate(new_edges)}

    for name, raw in overrides.items():
        param = by_name.get(name)
        if param is None:
            continue
        default_unit = param.default.unit if param.default else None
        q = coerce_quantity(raw, default_unit=default_unit)
        if q is None:
            continue
        _check_bounds(param, q)
        for path in param.targets:
            base, prop = _split_path(path)
            if base in node_idx:
                _set_property(new_nodes[node_idx[base]], prop, q)
            elif base in edge_idx:
                _set_property(new_edges[edge_idx[base]], prop, q)

    new_params = []
    for p in diagram.parameters:
        new_params.append(p)
    return diagram.model_copy(update={"nodes": new_nodes, "edges": new_edges, "parameters": new_params})


def sweep(
    diagram: Diagram, axis: Mapping[str, list]
) -> list[tuple[dict, Diagram]]:
    """Cartesian product of parameter values -> list of (overrides, diagram).

    Example::

        for overrides, d in sweep(diagram, {"R": [1e3, 1e4, 1e5]}):
            ...
    """
    from itertools import product

    names = list(axis.keys())
    values = [axis[n] for n in names]
    out: list[tuple[dict, Diagram]] = []
    for combo in product(*values):
        overrides = dict(zip(names, combo))
        out.append((overrides, apply_parameters(diagram, overrides)))
    return out


def _split_path(path: str) -> tuple[str, str]:
    if "." in path:
        base, prop = path.split(".", 1)
        return base, prop
    return path, "value"


def _set_property(obj: Node | Edge, prop: str, q: Quantity) -> None:
    props = dict(obj.properties)
    props[prop] = q
    obj.properties = props  # type: ignore[assignment]


def _check_bounds(p: Parameter, q: Quantity) -> None:
    if p.bounds is None:
        return
    lo, hi = p.bounds
    v = q.value
    if v < lo or v > hi:
        raise ValueError(
            f"parameter {p.name!r} value {v} outside bounds [{lo}, {hi}]"
        )
