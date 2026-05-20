"""Export a Diagram to GraphML via NetworkX."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.export.networkx_exporter import NetworkXExporter
from schemagraph.ir.schema import Diagram


class GraphMLExporter(Exporter):
    name = "graphml"
    default_extension = "graphml"
    binary = False

    def export(self, diagram: Diagram, **options: Any) -> str:
        import networkx as nx

        G = NetworkXExporter().export(diagram, **options)
        # NetworkX GraphML only accepts scalar attributes; coerce lists/dicts to strings.
        for _, data in G.nodes(data=True):
            _scalarize(data)
        for _, _, data in G.edges(data=True):
            _scalarize(data)

        buf = io.BytesIO()
        nx.write_graphml(G, buf, named_key_ids=True)
        return buf.getvalue().decode("utf-8")

    def write(self, diagram: Diagram, path, **options: Any) -> Path:
        path = Path(path)
        path.write_text(self.export(diagram, **options), encoding="utf-8")
        return path


def _scalarize(attrs: dict) -> None:
    for k, v in list(attrs.items()):
        if v is None:
            attrs[k] = ""
        elif isinstance(v, (list, dict, tuple)):
            import json

            attrs[k] = json.dumps(v, default=str)
        elif not isinstance(v, (str, int, float, bool)):
            attrs[k] = str(v)
