"""Spacecraft instrument catalog + per-instrument data sheets.

This subpackage extends schemagraph with:

- a curated YAML catalog of known instruments and their telemetry schemas,
- a :class:`SpacecraftAnnotator` that matches diagram nodes to catalog
  entries by label/alias,
- a sheet store (JSONL on disk) that lets you attach actual data to each
  instrument and query it,
- a CLI subcommand tree (``schemagraph instrument ...``) and an
  interactive REPL (``schemagraph shell``).
"""

from schemagraph.instruments.annotator import SpacecraftAnnotator
from schemagraph.instruments.catalog import (
    Catalog,
    InstrumentEntry,
    catalog_path,
    default_catalog,
    load_catalog,
)
from schemagraph.instruments.sheets import (
    SheetMissingError,
    SheetStore,
    sheet_id_for,
)

__all__ = [
    "Catalog",
    "InstrumentEntry",
    "SheetMissingError",
    "SheetStore",
    "SpacecraftAnnotator",
    "catalog_path",
    "default_catalog",
    "load_catalog",
    "sheet_id_for",
]
