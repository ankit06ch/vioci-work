"""Export a Diagram to a NetworkX graph (and optionally pickle to disk)."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram


def _node_attrs(node) -> dict:
    d = {
        "kind": node.kind,
        "label": node.label,
        "domain": node.domain,
        "confidence": node.confidence,
        "tags": list(node.tags),
        "provenance_stage": node.provenance.stage,
        "provenance_producer": node.provenance.producer,
    }
    for k, v in (node.properties or {}).items():
        d[f"prop_{k}"] = _coerce_attr(v)
    return d


def _edge_attrs(edge) -> dict:
    d = {
        "kind": edge.kind,
        "label": edge.label,
        "domain": edge.domain,
        "directed": edge.directed,
        "confidence": edge.confidence,
        "provenance_stage": edge.provenance.stage,
        "provenance_producer": edge.provenance.producer,
    }
    for k, v in (edge.properties or {}).items():
        d[f"prop_{k}"] = _coerce_attr(v)
    return d


def _coerce_attr(v):
    if hasattr(v, "value") and hasattr(v, "unit"):
        return f"{v.value} {v.unit}" if v.unit else v.value
    if isinstance(v, (list, dict, tuple)):
        import json

        return json.dumps(v, default=str)
    return v


class NetworkXExporter(Exporter):
    name = "networkx"
    default_extension = "gpickle"
    binary = True

    def export(self, diagram: Diagram, *, directed: bool | None = None, **options: Any):
        import networkx as nx

        any_directed = directed if directed is not None else any(e.directed for e in diagram.edges)
        G: Any = nx.MultiDiGraph() if any_directed else nx.MultiGraph()
        G.graph["id"] = diagram.id
        G.graph["schema_version"] = diagram.schema_version
        G.graph["domain"] = diagram.domain
        G.graph.update(diagram.metadata or {})

        for n in diagram.nodes:
            G.add_node(n.id, **_node_attrs(n))
        for e in diagram.edges:
            G.add_edge(e.source, e.target, key=e.id, **_edge_attrs(e))
        return G

    def write(self, diagram: Diagram, path, **options: Any) -> Path:
        path = Path(path)
        G = self.export(diagram, **options)
        with open(path, "wb") as fh:
            pickle.dump(G, fh)
        return path
