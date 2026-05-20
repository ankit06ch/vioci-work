"""Plugin registry behavior."""

from __future__ import annotations

import pytest

import schemagraph  # noqa: F401 - ensures built-ins are registered
from schemagraph.registry import (
    annotator_registry,
    exporter_registry,
    list_plugins,
)


def test_builtin_exporters_present():
    names = exporter_registry.names()
    assert "networkx" in names
    assert "graphml" in names
    assert "jsonld" in names


def test_builtin_annotators_present():
    names = annotator_registry.names()
    for name in ("generic", "electrical", "mechanical", "fluid", "thermal"):
        assert name in names


def test_load_unknown_raises():
    with pytest.raises(KeyError):
        exporter_registry.get("nope-format")


def test_list_plugins_shape():
    p = list_plugins()
    assert set(p.keys()) == {"exporters", "providers", "annotators"}
