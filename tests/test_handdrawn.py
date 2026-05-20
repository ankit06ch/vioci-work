"""Phase 4 tests: hand-drawn preprocessing + prompt variant + pipeline integration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from schemagraph.api import parse as api_parse
from schemagraph.cv.handdrawn import prepare_handdrawn, thin_strokes
from schemagraph.registry import provider_registry
from schemagraph.vlm.fake_provider import FakeProvider
from schemagraph.vlm.prompts import render_prompt


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _ensure_examples():
    if not (EXAMPLES / "handdrawn_rc_circuit.png").exists():
        from examples.generate_fixtures import main as gen

        gen()


_ensure_examples()


def test_handdrawn_prep_returns_clean_binary():
    img = (EXAMPLES / "handdrawn_rc_circuit.png").read_bytes()
    prep = prepare_handdrawn(img, correct_perspective=False)
    assert prep.binary.dtype == np.uint8
    # Should have a substantive amount of ink detected and not be all-white.
    ink_frac = (prep.binary > 0).mean()
    assert 0.005 < ink_frac < 0.5


def test_thin_strokes_preserves_topology():
    img = (EXAMPLES / "handdrawn_rc_circuit.png").read_bytes()
    prep = prepare_handdrawn(img, correct_perspective=False)
    skel = thin_strokes(prep.binary)
    # Skeleton should have fewer ink pixels than the original binary.
    assert (skel > 0).sum() < (prep.binary > 0).sum()


def test_handdrawn_prompt_variant_adds_heuristics():
    system_default, _ = render_prompt(
        "default", domain_hint="electrical", width=100, height=100
    )
    system_hd, _ = render_prompt(
        "handdrawn", domain_hint="electrical", width=100, height=100
    )
    assert len(system_hd) > len(system_default) + 200
    assert "wobbly" in system_hd.lower()
    assert "zig-zag" in system_hd.lower()
    assert "10kΩ" in system_hd


def test_handdrawn_flag_switches_prompt_variant_and_pipeline_runs():
    """Smoke-test that --handdrawn end-to-end produces a valid Diagram."""

    payload = {
        "_producer": "fake:hd",
        "domain": "electrical",
        "nodes": [
            {"id": "Vs", "kind": "voltage_source", "label": "Vs", "anchor": [50, 150], "properties": {"value": "9V"}, "confidence": 0.9},
            {"id": "R", "kind": "resistor", "label": "R", "anchor": [240, 150], "properties": {"value": "10kΩ"}, "confidence": 0.9},
            {"id": "C", "kind": "capacitor", "label": "C", "anchor": [430, 150], "properties": {"value": "1uF"}, "confidence": 0.85},
            {"id": "GND", "kind": "ground", "label": "GND", "anchor": [300, 280], "confidence": 0.85},
        ],
        "edges": [
            {"source": "Vs", "target": "R", "kind": "wire", "confidence": 0.85},
            {"source": "R", "target": "C", "kind": "wire", "confidence": 0.85},
            {"source": "C", "target": "GND", "kind": "wire", "confidence": 0.8},
            {"source": "Vs", "target": "GND", "kind": "wire", "confidence": 0.8},
        ],
    }

    def factory(**kwargs):
        return FakeProvider(payload=payload, **kwargs)

    provider_registry.register("fake-hd", factory)

    diagram = api_parse(
        EXAMPLES / "handdrawn_rc_circuit.png",
        provider="fake-hd",
        domain="electrical",
        handdrawn=True,
    )
    assert len(diagram.nodes) == 4
    # Hand-drawn-friendly preprocessing should still yield CV primitives.
    assert diagram.primitives is not None
    assert any(s.kind in {"line", "polyline"} for s in diagram.primitives.shapes)
