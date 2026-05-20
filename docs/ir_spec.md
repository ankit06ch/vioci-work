# IR Specification

The Intermediate Representation (IR) is defined as Pydantic v2 models in [`schemagraph/ir/schema.py`](../schemagraph/ir/schema.py). The JSON Schema for a `Diagram` can be printed with `schemagraph schema`.

## Top-level: `Diagram`

| Field            | Type                | Description |
| ---------------- | ------------------- | ----------- |
| `id`             | str                 | Stable content-hash id |
| `schema_version` | str                 | IR schema version |
| `source`         | `SourceMeta`        | Source file metadata + sha256 |
| `nodes`          | list[`Node`]        | Components / vertices |
| `edges`          | list[`Edge`]        | Connections |
| `constraints`    | list[`Constraint`]  | Equalities, boundary conditions, dimensions |
| `equations`      | list[`Equation`]    | Parsed equations |
| `datasets`       | list[`Dataset`]     | Extracted numerical data (plots, tables) |
| `parameters`     | list[`Parameter`]   | User-overridable parameters for sweeps |
| `geometry_layer` | `VectorLayer?`      | Vectorized geometry (native SVG or rasterized) |
| `primitives`     | `PrimitiveLayer?`   | Low-level CV primitives + OCR spans |
| `domain`         | str?                | Primary domain ("electrical", "mechanical", ...) |
| `metadata`       | dict                | Free-form provenance metadata |

## Graph elements

- **Node** — `id`, `kind` (`"resistor"`, `"beam"`, `"valve"`, `"block"`, `"vertex"`, ...), `label`, unit-aware `properties`, `ports`, optional `geometry`, `provenance`, `confidence`, `tags`.
- **Port** — `id`, `node_id`, `role` (e.g. `"anode"`, `"inlet"`, `"fixed_support"`), `position_px`, `direction`.
- **Edge** — `id`, `source`/`target` (node or port id), `source_port`/`target_port`, `kind` (`"wire"`, `"rigid_link"`, `"pipe"`, `"signal"`, `"graph_edge"`, ...), `directed`, `properties`, `polyline_px`, `provenance`, `confidence`.

## Physics-aware properties

`Node.properties` and `Edge.properties` map property name → `Quantity | str | float | int | bool | list | dict | None`. A `Quantity` is `{value, unit, raw, uncertainty}`. The unit string is a Pint-compatible expression. Annotators coerce raw label strings like `"10kΩ"` or `"1.5 µF"` into canonical Quantities.

## Constraints & equations

- **Constraint** — `kind` (`"equal"`, `"dimension"`, `"boundary_condition"`, `"fixed"`, `"inequality"`), `targets` (ids), optional `expression` (sympy-parseable) and `value`.
- **Equation** — `raw` text + best-effort `sympy_repr`, `lhs`, `rhs`, and a `variables` map binding free symbols to property paths like `"<node_id>.value"`.

## Stable IDs

All ids are SHA-256 digests over canonical JSON of the artifact's content (see [`schemagraph/ir/ids.py`](../schemagraph/ir/ids.py)). Re-parsing the same input produces identical ids, which is essential for caching, diffing, and golden-fixture evaluation.

## Provenance

Every node, edge, constraint, equation, and dataset carries a `Provenance` (`stage`, `producer`, `confidence`, `timestamp`, `notes`). This lets downstream consumers filter by source ("only edges grounded by CV"), audit confidence, and trace which model produced each artifact.
