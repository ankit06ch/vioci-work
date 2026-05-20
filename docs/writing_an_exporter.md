# Writing an exporter plugin

`schemagraph` exporters are Python classes implementing the [`Exporter`](../schemagraph/export/base.py) ABC. Registering one is a single line in your distribution's `pyproject.toml`.

## 1. Implement `Exporter`

```python
from typing import Any
from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity


class SpiceExporter(Exporter):
    name = "spice"
    default_extension = "cir"
    binary = False

    def export(self, diagram: Diagram, **options: Any) -> str:
        lines = [f"* schemagraph generated netlist: {diagram.id}"]
        node_index = diagram.node_index()
        for edge in diagram.edges:
            if edge.kind != "wire":
                continue
            src = self._spice_terminal(edge.source, node_index)
            dst = self._spice_terminal(edge.target, node_index)
            for n in (node_index.get(edge.source), node_index.get(edge.target)):
                if n is None:
                    continue
                lines.append(self._render_component(n, src, dst))
        lines.append(".end")
        return "\n".join(lines)
```

## 2. Register via entry points

```toml
[project.entry-points."schemagraph.exporters"]
spice = "schemagraph_spice:SpiceExporter"
```

After `pip install -e .` your exporter is automatically available:

```bash
schemagraph exporters list      # shows "spice"
schemagraph export d.json --format spice --out d.cir
```

## Conventions

- `name` becomes the public format name (`--format <name>`).
- `default_extension` is informational and used by tooling.
- For binary outputs (e.g. HDF5, protobuf) set `binary = True` and override `write` to avoid double-encoding.
- Respect `Diagram.domain` and per-node `domain` — many diagrams are multi-domain. Exporters should ignore nodes outside their domain rather than fail.
- Coerce `Quantity` instances explicitly; downstream simulators usually require specific units.

## Testing your exporter

A minimal sanity test imports your exporter, builds a tiny `Diagram` in code, and asserts the output contains the expected structure. See [`tests/test_pipeline_e2e.py`](../tests/test_pipeline_e2e.py) for a working example using the built-in exporters.
