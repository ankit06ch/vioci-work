"""Shared pytest fixtures."""

from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient

from server import workspace
from server.main import app
from server.settings import reset_server_settings


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("VIOCI_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIOCI_SQLITE_PATH", str(tmp_path / "idx.sqlite"))
    monkeypatch.delenv("VIOCI_DATABASE_URL", raising=False)
    monkeypatch.delenv("VIOCI_SUPABASE_URL", raising=False)
    monkeypatch.delenv("VIOCI_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path / "ws")
    reset_server_settings()
    import server.state as state

    if state._engine is not None:
        state._engine.dispose()
    state._engine = None
    import server.events as events

    events._subscribers.clear()
    with TestClient(app) as c:
        c.get("/api/health")
        c.post(
            "/api/auth/signup",
            json={
                "email": f"test-{uuid.uuid4().hex[:8]}@vioci.local",
                "password": "testpass123",
                "full_name": "Test User",
            },
        )
        yield c
    if state._engine is not None:
        state._engine.dispose()
        state._engine = None


@pytest.fixture
def small_rc_circuit_png() -> bytes:
    """Tiny synthetic image of an RC-like sketch.

    Two rectangles ("R" and "C") connected by horizontal lines, with a
    bottom rail. Used by CV tests to ensure primitives are detected.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 200), "white")
    d = ImageDraw.Draw(img)
    # Boxes (rectangles) with a small gap between wires & boxes so connected
    # components are separable, matching well-drawn schematic conventions.
    d.rectangle([80, 70, 140, 110], outline="black", width=3)  # resistor
    d.rectangle([260, 70, 320, 110], outline="black", width=3)  # capacitor
    # wires
    d.line([20, 90, 78, 90], fill="black", width=3)
    d.line([142, 90, 258, 90], fill="black", width=3)
    d.line([322, 90, 380, 90], fill="black", width=3)
    # ground rail
    d.line([20, 160, 380, 160], fill="black", width=3)
    d.line([20, 92, 20, 160], fill="black", width=3)
    d.line([380, 92, 380, 160], fill="black", width=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fake_vlm_payload() -> dict:
    """A VLM-like payload matching small_rc_circuit_png."""
    return {
        "_producer": "fake:test-model",
        "domain": "electrical",
        "nodes": [
            {
                "id": "R1",
                "kind": "resistor",
                "label": "10k",
                "anchor": [110, 90],
                "properties": {"value": "10kΩ"},
                "confidence": 0.95,
            },
            {
                "id": "C1",
                "kind": "capacitor",
                "label": "1uF",
                "anchor": [290, 90],
                "properties": {"value": "1uF"},
                "confidence": 0.95,
            },
            {
                "id": "GND",
                "kind": "ground",
                "label": "GND",
                "anchor": [200, 160],
                "confidence": 0.9,
            },
        ],
        "edges": [
            {
                "source": "R1",
                "target": "C1",
                "kind": "wire",
                "polyline": [[140, 90], [260, 90]],
                "confidence": 0.9,
            },
            {
                "source": "C1",
                "target": "GND",
                "kind": "wire",
                "polyline": [[290, 110], [290, 160]],
                "confidence": 0.8,
            },
        ],
        "constraints": [
            {
                "kind": "boundary_condition",
                "targets": ["GND"],
                "expression": "V = 0",
            }
        ],
        "equations": [{"raw": "tau = R*C"}],
        "parameters": [
            {
                "name": "R",
                "default": {"value": 10000.0, "unit": "ohm"},
                "bounds": [1000.0, 1000000.0],
                "targets": ["R1.value"],
            }
        ],
    }
