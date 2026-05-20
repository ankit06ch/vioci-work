"""schemagraph.export: pluggable exporters to interoperable graph formats."""

from schemagraph.export.base import Exporter, load_exporter
from schemagraph.export.graphml_exporter import GraphMLExporter
from schemagraph.export.jsonld_exporter import JSONLDExporter
from schemagraph.export.networkx_exporter import NetworkXExporter
from schemagraph.registry import exporter_registry

# Built-in registration (entry-point-discovered plugins override these by name).
exporter_registry.register("networkx", NetworkXExporter)
exporter_registry.register("graphml", GraphMLExporter)
exporter_registry.register("jsonld", JSONLDExporter)

__all__ = [
    "Exporter",
    "load_exporter",
    "NetworkXExporter",
    "GraphMLExporter",
    "JSONLDExporter",
]
