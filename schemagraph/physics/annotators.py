"""Domain-aware physics annotators.

An annotator takes a :class:`Diagram` and enriches it with unit-aware
properties, parsed equations, and parametric placeholders, without
otherwise changing the graph topology.

Phase 0 provides the registry and a generic annotator that performs
unit-aware string-to-Quantity coercion. Phase 3 fleshes out the domain
annotators (electrical / mechanical / fluid / thermal) with kind-specific
default units and equations.
"""

from __future__ import annotations

import abc
from typing import Any

from schemagraph.ir import ids as _ids
from schemagraph.ir.schema import Constraint, Diagram, Equation, Node, Provenance
from schemagraph.physics.equations import parse_equation, resolve_variables
from schemagraph.physics.units import coerce_quantity
from schemagraph.registry import annotator_registry


class Annotator(abc.ABC):
    """Abstract domain annotator.

    Subclasses contribute:

    - :attr:`default_units` mapping `node.kind` to an SI unit string used
      when coercing labels and ``value`` properties.
    - :meth:`extra_constraints` returning auto-detected constraints for
      well-known kinds (e.g. electrical "ground" -> ``V = 0``, mechanical
      "fixed_support" -> ``u = 0, theta = 0``).
    """

    name: str = "abstract"
    default_units: dict[str, str] = {}

    def annotate(self, diagram: Diagram) -> Diagram:
        prov = Provenance(stage="annotator", producer=f"{self.__class__.__name__}")
        new_nodes = [self._annotate_node(n, prov) for n in diagram.nodes]
        new_equations = self._annotate_equations(diagram.equations, new_nodes, diagram.parameters, prov)
        added_constraints = self.extra_constraints(diagram, new_nodes, prov)
        all_constraints = list(diagram.constraints) + added_constraints
        return diagram.model_copy(
            update={
                "nodes": new_nodes,
                "equations": new_equations,
                "constraints": all_constraints,
                "domain": diagram.domain or self.name,
            }
        )

    def _annotate_node(self, node: Node, prov: Provenance) -> Node:
        default = self.default_units.get(node.kind)
        new_props = dict(node.properties)
        for k, v in list(new_props.items()):
            coerced = coerce_quantity(
                v, default_unit=default if k in {"value", "magnitude"} else None
            )
            if coerced is not None:
                new_props[k] = coerced
        if node.label and "value" not in new_props:
            coerced = coerce_quantity(node.label, default_unit=default)
            if coerced is not None and coerced.unit is not None:
                new_props["value"] = coerced
        return node.model_copy(
            update={"properties": new_props, "domain": node.domain or self.name}
        )

    def _annotate_equations(
        self,
        equations: list[Equation],
        nodes: list[Node],
        parameters: list,
        prov: Provenance,
    ) -> list[Equation]:
        out: list[Equation] = []
        for eq in equations:
            sympy_repr, symbols, lhs, rhs = parse_equation(eq.raw)
            variables = dict(eq.variables) if eq.variables else {}
            if symbols:
                resolved = resolve_variables(symbols, nodes=nodes, parameters=parameters)
                for k, v in resolved.items():
                    variables.setdefault(k, v)
            out.append(
                eq.model_copy(
                    update={
                        "sympy_repr": sympy_repr or eq.sympy_repr,
                        "lhs": lhs or eq.lhs,
                        "rhs": rhs or eq.rhs,
                        "variables": variables,
                        "provenance": prov if sympy_repr else eq.provenance,
                    }
                )
            )
        return out

    def extra_constraints(
        self, diagram: Diagram, nodes: list[Node], prov: Provenance
    ) -> list[Constraint]:
        return []


class GenericAnnotator(Annotator):
    name = "generic"
    default_units: dict[str, str] = {}


class ElectricalAnnotator(Annotator):
    name = "electrical"
    default_units = {
        "resistor": "ohm",
        "capacitor": "farad",
        "inductor": "henry",
        "voltage_source": "volt",
        "current_source": "ampere",
        "diode": "volt",
        "battery": "volt",
        "ground": "volt",
    }

    def extra_constraints(self, diagram, nodes, prov):
        out: list[Constraint] = []
        for n in nodes:
            if n.kind == "ground":
                out.append(
                    Constraint(
                        id=_ids.constraint_id(diagram.id, "boundary_condition", [n.id], "V = 0"),
                        kind="boundary_condition",
                        targets=[n.id],
                        expression="V = 0",
                        provenance=prov,
                    )
                )
        return out


class MechanicalAnnotator(Annotator):
    name = "mechanical"
    default_units = {
        "beam": "meter",
        "mass": "kilogram",
        "spring": "newton/meter",
        "damper": "newton*second/meter",
        "force": "newton",
        "moment": "newton*meter",
        "support": "meter",
    }

    def extra_constraints(self, diagram, nodes, prov):
        out: list[Constraint] = []
        for n in nodes:
            if n.kind in {"fixed_support", "fixed", "anchor"}:
                out.append(
                    Constraint(
                        id=_ids.constraint_id(diagram.id, "fixed", [n.id], "u = 0; theta = 0"),
                        kind="fixed",
                        targets=[n.id],
                        expression="u = 0; theta = 0",
                        provenance=prov,
                    )
                )
            elif n.kind in {"roller", "roller_support"}:
                out.append(
                    Constraint(
                        id=_ids.constraint_id(diagram.id, "roller", [n.id], "u_n = 0"),
                        kind="roller",
                        targets=[n.id],
                        expression="u_n = 0",
                        provenance=prov,
                    )
                )
        return out


class FluidAnnotator(Annotator):
    name = "fluid"
    default_units = {
        "pipe": "meter",
        "valve": "pascal",
        "pump": "watt",
        "reservoir": "meter**3",
        "flow_rate": "meter**3/second",
    }


class ThermalAnnotator(Annotator):
    name = "thermal"
    default_units = {
        "thermal_resistance": "kelvin/watt",
        "thermal_capacitance": "joule/kelvin",
        "heat_source": "watt",
        "temperature": "kelvin",
    }


class ControlAnnotator(Annotator):
    """Control-systems block diagrams: gain, time-constant, frequency."""

    name = "control"
    default_units = {
        "gain": "dimensionless",
        "integrator": "second",
        "lowpass": "second",
        "delay": "second",
        "filter": "hertz",
    }


class GraphAnnotator(Annotator):
    """Plotted-data graphs: leaves values un-typed but normalizes axis units."""

    name = "graph"
    default_units: dict[str, str] = {}


# Built-in registration -----------------------------------------------------
annotator_registry.register("generic", GenericAnnotator)
annotator_registry.register("electrical", ElectricalAnnotator)
annotator_registry.register("mechanical", MechanicalAnnotator)
annotator_registry.register("fluid", FluidAnnotator)
annotator_registry.register("thermal", ThermalAnnotator)
annotator_registry.register("control", ControlAnnotator)
annotator_registry.register("graph", GraphAnnotator)


def load_annotator(name: str, **kwargs: Any) -> Annotator:
    factory = annotator_registry.get(name)
    return factory(**kwargs)
