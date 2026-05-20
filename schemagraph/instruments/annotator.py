"""SpacecraftAnnotator: enrich diagram nodes with telemetry schemas.

Walks every Node in a Diagram, tries to match its ``label`` (and ``kind``)
against the catalog, and attaches:

- ``properties["telemetry_schema"]`` — list of {name, unit, dtype} dicts,
- ``properties["data_product"]`` — coarse data-product class,
- ``properties["sheet_id"]`` — deterministic key the SheetStore uses,
- ``properties["instrument_id"]`` — catalog entry id (canonical name).

Nodes that don't match any catalog entry are left alone.
"""

from __future__ import annotations

from typing import Any

from schemagraph.instruments.catalog import Catalog, default_catalog
from schemagraph.instruments.sheets import sheet_id_for
from schemagraph.ir.schema import Constraint, Diagram, Node, Provenance
from schemagraph.physics.annotators import Annotator
from schemagraph.registry import annotator_registry


class SpacecraftAnnotator(Annotator):
    """Domain annotator for spacecraft callout/assembly diagrams."""

    name = "spacecraft"

    def __init__(self, catalog: Catalog | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._catalog = catalog or default_catalog()

    def annotate(self, diagram: Diagram) -> Diagram:
        prov = Provenance(stage="annotator", producer="SpacecraftAnnotator")
        new_nodes = [self._enrich(n, prov) for n in diagram.nodes]
        return diagram.model_copy(
            update={
                "nodes": new_nodes,
                "domain": diagram.domain or self.name,
            }
        )

    def _enrich(self, node: Node, prov: Provenance) -> Node:
        # Try label first, then kind, then their concatenation.
        candidates = [node.label, node.kind, f"{node.label} {node.kind}"]
        entry = None
        for c in candidates:
            if not c:
                continue
            entry = self._catalog.match(c)
            if entry is not None:
                break
        if entry is None:
            return node

        new_props = dict(node.properties)
        new_props["instrument_id"] = entry.id
        new_props["display_name"] = entry.display_name
        new_props["data_product"] = entry.data_product
        new_props["telemetry_schema"] = entry.telemetry_fields
        new_props["sheet_id"] = sheet_id_for(entry.id, node.id)

        return node.model_copy(
            update={
                "kind": node.kind or "instrument",
                "domain": "spacecraft",
                "properties": new_props,
                "provenance": prov,
                "tags": list(node.tags or []) + ["catalog_matched"],
            }
        )


annotator_registry.register("spacecraft", SpacecraftAnnotator)
