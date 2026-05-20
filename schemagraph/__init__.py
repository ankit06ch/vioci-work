"""schemagraph: schematic/diagram/graph -> structured IR -> interoperable exports."""

from __future__ import annotations

from importlib import metadata as _metadata

try:
    __version__ = _metadata.version("schemagraph")
except _metadata.PackageNotFoundError:
    __version__ = "0.1.0"

from schemagraph.ir.schema import (
    Diagram,
    Edge,
    Equation,
    Constraint,
    Dataset,
    GeometryRef,
    Node,
    Port,
    Provenance,
    Quantity,
    SourceMeta,
    VectorLayer,
)
from schemagraph.api import annotate, apply_parameters, export, parse, sweep, validate

# Side-effect: register built-in domain exporters and simulators in the plugin registry.
from schemagraph import domain_exporters as _domain_exporters  # noqa: F401
from schemagraph import simulate as _simulate_pkg  # noqa: F401
from schemagraph.simulate import simulate

__all__ = [
    "__version__",
    "Diagram",
    "Node",
    "Edge",
    "Port",
    "Constraint",
    "Equation",
    "Dataset",
    "GeometryRef",
    "VectorLayer",
    "Provenance",
    "Quantity",
    "SourceMeta",
    "parse",
    "annotate",
    "validate",
    "export",
    "apply_parameters",
    "sweep",
    "simulate",
]
