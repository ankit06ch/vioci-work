"""Launch readiness JSON import and upload guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "schemagraph/launch_compat/schema/samples/vioci_leo_observation_sat.json"
)


@pytest.fixture
def sample_bytes() -> bytes:
    return SAMPLE.read_bytes()


def test_upload_rejects_launch_json(client, sample_bytes):
    r = client.post(
        "/api/projects/upload",
        files=[("files", ("vioci_leo_observation_sat.json", sample_bytes, "application/json"))],
    )
    assert r.status_code == 400
    assert "Launch tab" in r.json()["detail"]


def test_import_launch_readiness(client, sample_bytes, small_rc_circuit_png):
    r = client.post(
        "/api/projects/upload",
        files=[("files", ("circuit.png", small_rc_circuit_png, "image/png"))],
    )
    assert r.status_code == 200
    pid = r.json()["projects"][0]["id"]

    r2 = client.post(
        f"/api/projects/{pid}/launch-readiness/import",
        files=[("file", ("vioci_leo_observation_sat.json", sample_bytes, "application/json"))],
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ok"] is True
    assert body["check_readiness"]["ready_count"] >= 15

    from schemagraph.launch_compat.schema.builder import load_launch_readiness

    doc = load_launch_readiness(pid)
    assert doc is not None
    assert doc["mission"]["mass_kg"] == 142.0

    r3 = client.get(f"/api/projects/{pid}/schema-registry/explorer-file/launch_schema")
    assert r3.status_code == 200
    assert '"SatelliteLaunchReadiness"' in r3.text
