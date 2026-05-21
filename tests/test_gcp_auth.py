import json
import os

import pytest

from server.gcp_auth import configure_vertex_adc


def test_configure_vertex_adc_writes_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    key = {"type": "service_account", "project_id": "p", "private_key": "x"}
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", json.dumps(key))
    path = tmp_path / "adc.json"
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_PATH", str(path))

    out = configure_vertex_adc()

    assert out == str(path)
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(path)
    assert json.loads(path.read_text()) == key


def test_configure_vertex_adc_skips_when_path_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/existing.json")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", '{"type":"service_account"}')

    assert configure_vertex_adc() == "/existing.json"


def test_configure_vertex_adc_invalid_json(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "not-json")

    with pytest.raises(RuntimeError, match="not valid JSON"):
        configure_vertex_adc()
