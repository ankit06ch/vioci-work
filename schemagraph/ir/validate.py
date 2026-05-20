"""Cross-field IR validation.

These checks go beyond what pydantic's schema validation does in
``schemagraph.ir.schema`` — they verify *referential* and *semantic*
consistency of a fully-assembled Diagram.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from schemagraph.ir.schema import Diagram


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    target: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add(self, severity: str, code: str, message: str, target: str | None = None) -> None:
        self.issues.append(ValidationIssue(severity, code, message, target))

    def extend(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def __bool__(self) -> bool:  # truthy if any issues
        return bool(self.issues)


def validate_diagram(diagram: Diagram) -> ValidationReport:
    """Run all cross-field validators against a Diagram."""

    report = ValidationReport()

    node_ids = {n.id for n in diagram.nodes}
    port_ids = {p.id: p for n in diagram.nodes for p in n.ports}
    edge_ids = {e.id for e in diagram.edges}

    # --- nodes -----------------------------------------------------------
    for node in diagram.nodes:
        for port in node.ports:
            if port.node_id != node.id:
                report.add(
                    "error",
                    "PORT_BAD_NODE_REF",
                    f"port {port.id} declares node_id={port.node_id!r} but is on node {node.id!r}",
                    port.id,
                )

    # --- edges -----------------------------------------------------------
    for edge in diagram.edges:
        for endpoint_name, endpoint_id, port_attr in (
            ("source", edge.source, edge.source_port),
            ("target", edge.target, edge.target_port),
        ):
            if endpoint_id not in node_ids and endpoint_id not in port_ids:
                report.add(
                    "error",
                    "EDGE_DANGLING_ENDPOINT",
                    f"edge {edge.id} {endpoint_name}={endpoint_id!r} does not match any node or port",
                    edge.id,
                )
            if port_attr is not None and port_attr not in port_ids:
                # Downgraded to warning: the node-level endpoint is valid and
                # downstream exporters (SPICE, NetworkX, etc.) only need that.
                # VLMs commonly invent generic port names like "in"/"out" that
                # don't correspond to any explicitly modeled Port.
                report.add(
                    "warning",
                    "EDGE_DANGLING_PORT",
                    f"edge {edge.id} {endpoint_name}_port={port_attr!r} not found "
                    f"(node endpoint is valid; port ref will be ignored downstream)",
                    edge.id,
                )

    # --- constraints -----------------------------------------------------
    all_refs = node_ids | set(port_ids) | edge_ids | {p.id for p in diagram.parameters}
    for c in diagram.constraints:
        for t in c.targets:
            base = t.split(".", 1)[0]
            if base not in all_refs:
                report.add(
                    "warning",
                    "CONSTRAINT_DANGLING_TARGET",
                    f"constraint {c.id} references unknown target {t!r}",
                    c.id,
                )

    # --- equations -------------------------------------------------------
    for eq in diagram.equations:
        for var, ref in eq.variables.items():
            base = ref.split(".", 1)[0]
            if base not in all_refs:
                report.add(
                    "warning",
                    "EQUATION_DANGLING_VARIABLE",
                    f"equation {eq.id} variable {var!r} references unknown {ref!r}",
                    eq.id,
                )

    # --- parameters ------------------------------------------------------
    for p in diagram.parameters:
        for t in p.targets:
            base = t.split(".", 1)[0]
            if base not in all_refs:
                report.add(
                    "warning",
                    "PARAMETER_DANGLING_TARGET",
                    f"parameter {p.id} targets unknown {t!r}",
                    p.id,
                )

    # --- weak structural sanity -----------------------------------------
    if not diagram.nodes and not diagram.datasets:
        report.add(
            "warning",
            "EMPTY_DIAGRAM",
            "diagram has no nodes and no datasets; downstream exports will be trivial",
        )

    return report
