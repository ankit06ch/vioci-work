# schemagraph

> Ingest hand-drawn and digital schematics, diagrams, and graphs and convert them into structured, machine-readable representations suitable for simulation, optimization, and AI reasoning.

`schemagraph` is a Python library and CLI that fuses classical computer vision with cloud multimodal LLMs to extract **components, connections, labels, dimensions, constraints, equations, vectorized geometry, and numerical datasets** from a diagram into a normalized **Intermediate Representation (IR)**. The IR is then exported to interoperable graph formats (NetworkX, GraphML, JSON-LD) in v1, and to domain-specific simulation formats (SPICE, URDF, Modelica, FEniCS, OpenFOAM, orbital toolchains) via plugin exporters.

## Why

Existing tools either (a) understand schematics in a single domain (e.g. EDA tools that only do electrical), or (b) produce raw OCR with no semantic graph. `schemagraph` produces a **domain-agnostic graph IR** with unit-aware physical properties and parametric placeholders so the same input can drive arbitrary downstream simulators under arbitrary user-defined parameters.

## High-level pipeline

```
Image / PDF / SVG
   |
   v
[Ingest & normalize]  ----+
   |                      |
   v                      v
[CV primitives]      [Multimodal VLM]
   \                    /
    \                  /
     v                v
   [IR fusion & validation]
        |
        v
   [Physics annotation: units, equations, parametric placeholders]
        |
        v
   Normalized IR  ---->  NetworkX / GraphML / JSON-LD
                           (plugin: SPICE / URDF / FEniCS / OpenFOAM / Modelica / orbital)
```

## Install

```bash
pip install -e ".[openai,dev]"
```

Optional extras:

- `openai`, `anthropic`, `google` — cloud VLM clients (pick whichever you have keys for)
- `ocr-tesseract`, `ocr-paddle` — OCR backends for label extraction
- `all-providers` — all three VLM SDKs
- `web` — FastAPI dev server for the local web UI (`server/`, `make dev`)

## Web UI (local)

Full-stack browser app: upload diagrams, watch parse progress over WebSockets, inspect nodes (telemetry schema + CSV sheets), chat with Gemini about a node or the whole diagram, and run parameter sweeps / `analytic_rc` simulation.

```bash
pip install -e ".[web,google,dev]"
cd webapp && npm install
# from repo root:
make dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173). The Vite dev server proxies `/api` and WebSockets to FastAPI on port **8000**. Configure the same VLM credentials as the CLI (for example Vertex or `GOOGLE_API_KEY` in `.env`).

### Cloud database (free)

By default, data lives under `workspace/` (SQLite + files). To use **Supabase** on the free tier (Postgres + optional file storage), copy `.env.example` to `.env`, follow [docs/cloud-setup.md](docs/cloud-setup.md), install `pip install -e ".[web,cloud,google]"`, and run `PYTHONPATH=. python scripts/check_cloud.py`.

In the UI, **parsing always uses Google Gemini**; **hand-drawn vs clean** raster handling and the **annotation domain** (electrical, spacecraft, generic, …) are chosen automatically from the image and fused graph (`schemagraph.autodetect`).

## HTTP API

The web UI is a client of the same **REST + WebSocket API** served by FastAPI:

| Resource | Endpoints |
|----------|-----------|
| Projects | `POST /api/projects/upload`, `GET /api/projects`, `GET/DELETE /api/projects/{id}`, `GET …/image`, `GET …/diagram` |
| Parse | `POST /api/projects/{id}/parse` (async; watch `WS /api/projects/{id}/events`) |
| Sheets | `POST/GET /api/projects/{id}/sheets/{node_id}/…` |
| Chat | `POST /api/projects/{id}/chat`, `POST …/chat/{node_id}` |
| Simulate | `POST /api/projects/{id}/simulate`, `POST …/sweep` |

- **Human docs:** [http://127.0.0.1:5173/docs](http://127.0.0.1:5173/docs) (in-app guide + curl examples)
- **OpenAPI:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) (Swagger) · [ReDoc](http://127.0.0.1:8000/api/redoc) · `GET /api/openapi.json`
- **Index:** `GET /api` returns version and doc links

Source of truth for the in-app reference: `webapp/src/api/reference.ts`.

## Quick start

```bash
# Parse a diagram to IR JSON
schemagraph parse examples/electrical_rc_circuit.png \
    --provider openai \
    --out diagram.json

# Validate the IR
schemagraph validate diagram.json

# Attach physics annotations (units, equations, parametric placeholders)
schemagraph annotate diagram.json --domain electrical --out diagram.annotated.json

# Export to a graph format
schemagraph export diagram.annotated.json --format graphml --out graph.graphml
schemagraph export diagram.annotated.json --format jsonld  --out graph.jsonld
schemagraph export diagram.annotated.json --format networkx --out graph.gpickle

# Discover plugins
schemagraph providers list
schemagraph exporters list
```

You can also use the library directly:

```python
from schemagraph import parse, annotate, export

diagram = parse("examples/electrical_rc_circuit.png", provider="openai")
diagram = annotate(diagram, domain="electrical")
export(diagram, format="graphml", path="graph.graphml")
```

## Intermediate Representation (IR)

The IR is the contract that decouples extraction from downstream consumers. A `Diagram` contains:

- **nodes** — components with `kind`, `label`, unit-aware `properties`, `ports`, `geometry`, and `provenance`
- **edges** — connections with `kind`, source/target (port-aware), `properties`, `polyline_px`, and `provenance`
- **constraints** — equalities, dimensions, boundary conditions, fixed-supports, etc.
- **equations** — parsed via sympy; variables resolved against node/edge property paths
- **datasets** — extracted plotted data (axes + values) when the input is a graph/plot
- **geometry_layer** — vectorized SVG-like geometry preserved alongside the semantic graph
- **metadata + provenance** — which stage/model produced each artifact, with confidence

See [`docs/ir_spec.md`](docs/ir_spec.md).

## Plugin architecture

Exporters, VLM providers, and physics annotators are registered via Python entry points:

```
[project.entry-points."schemagraph.exporters"]
graphml = "my_pkg.my_module:MyExporter"
```

See [`docs/writing_an_exporter.md`](docs/writing_an_exporter.md).

## Roadmap

- **Phase 0** Foundation: IR schema, CLI, provider/exporter ABCs, plugin registry, units.
- **Phase 1** MVP pipeline: ingest -> CV -> OpenAI VLM -> IR -> NetworkX/GraphML/JSON-LD.
- **Phase 2** Multi-provider + eval harness.
- **Phase 3** Physics layer: sympy equations, parametric placeholders, constraints.
- **Phase 4** Hand-drawn robustness.
- **Phase 5** Domain exporter plugins: SPICE, URDF, Modelica, FEniCS, OpenFOAM, orbital.
- **Phase 6** Simulation execution adapters.

## License

MIT
