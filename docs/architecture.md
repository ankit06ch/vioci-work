# Architecture

`schemagraph` is structured around a single canonical Intermediate Representation (IR). Every stage either produces or consumes IR fragments; new domains and exporters are added without touching the core.

```
                ingest                cv                vlm
input file  -->  raster + meta  -->  primitives  -->  semantic JSON
                                                            |
                                       fusion <--------------'
                                          |
                                        ir.Diagram (validated)
                                          |
                                  physics annotators (units, equations)
                                          |
                              exporters: networkx / graphml / jsonld
                                          |
                              (plugins: spice / urdf / fenics / openfoam / modelica / orbital)
```

## Stages

1. **ingest** ([`schemagraph/ingest`](../schemagraph/ingest)) — load PNG/JPG/PDF/SVG, normalize raster (deskew, denoise, resize), and preserve native vector geometry from SVG when present.
2. **cv** ([`schemagraph/cv`](../schemagraph/cv)) — classical CV primitive extraction: lines (Hough), rectangles & circles (contour fitting), junction dots, and OCR text spans. Output is a `PrimitiveLayer` — *not yet semantic*.
3. **vlm** ([`schemagraph/vlm`](../schemagraph/vlm)) — provider-agnostic multimodal extraction. The image plus `PrimitiveLayer` (as structural hints) is sent to a VLM that returns structured JSON conforming to `extraction_json_schema()`.
4. **ir.builder** ([`schemagraph/ir/builder.py`](../schemagraph/ir/builder.py)) — fuses the VLM payload with CV primitives: nodes are snapped to detected shapes, edges are reconciled against detected polylines (hallucinated connections without pixel support are downgraded), stable content-hash IDs are assigned, and a `Diagram` is constructed.
5. **ir.validate** ([`schemagraph/ir/validate.py`](../schemagraph/ir/validate.py)) — cross-field invariants: dangling refs, port arity, unit coherence.
6. **physics.annotators** ([`schemagraph/physics/annotators.py`](../schemagraph/physics/annotators.py)) — domain-aware Quantity coercion (`"10kΩ"` → `Quantity(10000, "ohm")`), equation parsing, parametric placeholders.
7. **export** ([`schemagraph/export`](../schemagraph/export)) — plugin-discovered exporters. v1 ships NetworkX, GraphML, JSON-LD.

## Plugin system

`schemagraph.registry` provides three registries (`exporter_registry`, `provider_registry`, `annotator_registry`). Each registry:

- exposes built-in factories registered via `register(name, factory)`,
- lazily discovers third-party factories via Python entry points (`schemagraph.exporters`, `schemagraph.providers`, `schemagraph.annotators`),
- resolves entry-point plugins before built-ins so third parties can override behavior.

A domain exporter package (e.g. `schemagraph-spice`) needs only to declare:

```toml
[project.entry-points."schemagraph.exporters"]
spice = "schemagraph_spice:SpiceExporter"
```

…and `SpiceExporter` becomes available as `schemagraph export --format spice` and via `schemagraph.api.export(diagram, format="spice")`.

## Why pixel-grounded fusion?

A naive pipeline that trusts the VLM end-to-end will frequently hallucinate connections that aren't actually drawn (especially on dense schematics). The IR builder uses CV-detected lines as ground truth for *pixel support*: predicted edges whose mid-points are far from any detected line are downgraded in confidence. This dramatically improves precision without sacrificing the VLM's semantic strengths (recognizing component kinds, reading labels, picking up equations).
