"""Ensemble provider behavior: fallback and merge modes."""

from __future__ import annotations

import pytest

from schemagraph.vlm.base import ExtractionRequest
from schemagraph.vlm.ensemble import EnsembleProvider
from schemagraph.vlm.fake_provider import FakeProvider


class _BrokenProvider(FakeProvider):
    def extract(self, request):
        raise RuntimeError("boom")


def _req() -> ExtractionRequest:
    return ExtractionRequest(image_bytes=b"")


def test_fallback_skips_broken_provider():
    good = FakeProvider(payload={"nodes": [{"id": "a", "kind": "r"}], "edges": []})
    ens = EnsembleProvider(providers=[_BrokenProvider(), good], mode="fallback")
    resp = ens.extract(_req())
    assert resp.payload["nodes"][0]["id"] == "a"


def test_fallback_raises_when_all_fail():
    ens = EnsembleProvider(providers=[_BrokenProvider(), _BrokenProvider()], mode="fallback")
    with pytest.raises(RuntimeError):
        ens.extract(_req())


def test_merge_picks_higher_confidence_per_node():
    a = FakeProvider(payload={
        "nodes": [{"id": "R1", "kind": "resistor", "label": "a", "confidence": 0.5}],
        "edges": [],
    })
    b = FakeProvider(payload={
        "nodes": [{"id": "R1", "kind": "resistor", "label": "b", "confidence": 0.9}],
        "edges": [],
    })
    ens = EnsembleProvider(providers=[a, b], mode="ensemble")
    resp = ens.extract(_req())
    nodes = resp.payload["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["label"] == "b"


def test_merge_concats_constraints_and_equations():
    a = FakeProvider(payload={
        "nodes": [],
        "edges": [],
        "equations": [{"raw": "F = m*a"}],
    })
    b = FakeProvider(payload={
        "nodes": [],
        "edges": [],
        "equations": [{"raw": "tau = R*C"}],
    })
    ens = EnsembleProvider(providers=[a, b], mode="ensemble")
    resp = ens.extract(_req())
    eqs = {e["raw"] for e in resp.payload["equations"]}
    assert eqs == {"F = m*a", "tau = R*C"}
