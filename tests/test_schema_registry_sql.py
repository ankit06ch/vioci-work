from __future__ import annotations

import pytest

from server.schema_registry import build_tables, write_registry_files
from server.schema_registry_sql import append_row, delete_row, run_sql, update_row


def _seed_project(tmp_path, monkeypatch, pid: str = "sql-proj") -> None:
    monkeypatch.setattr("server.schema_registry.project_dir", lambda x: tmp_path / x)
    monkeypatch.setattr("server.workspace.project_dir", lambda x: tmp_path / x)
    monkeypatch.setattr("server.workspace.ensure_workspace", lambda: tmp_path)
    monkeypatch.setattr("server.workspace._use_cloud_files", lambda: False)
    doc = build_tables(
        project_id=pid,
        project_name="t",
        parse_status="done",
        last_domain=None,
        diagram={
            "nodes": [{"id": "n1", "label": "A", "kind": "x"}],
            "edges": [{"id": "e1", "source": "n1", "target": "n1", "kind": "loop"}],
        },
        annotations=[],
    )
    write_registry_files(pid, doc)


def test_run_sql_select(tmp_path, monkeypatch):
    _seed_project(tmp_path, monkeypatch)
    out = run_sql("sql-proj", "SELECT label FROM components")
    assert out["mutated"] is False
    assert out["rows"][0]["label"] == "A"


def test_update_row_persists(tmp_path, monkeypatch):
    _seed_project(tmp_path, monkeypatch)
    update_row("sql-proj", "components", 0, {"mass_kg": "42"})
    out = run_sql("sql-proj", "SELECT mass_kg FROM components")
    assert out["rows"][0]["mass_kg"] == "42"


def test_delete_row(tmp_path, monkeypatch):
    _seed_project(tmp_path, monkeypatch)
    append_row("sql-proj", "components", {"name": "extra"})
    delete_row("sql-proj", "components", 1)
    out = run_sql("sql-proj", "SELECT COUNT(*) AS c FROM components")
    assert int(out["rows"][0]["c"]) == 1


def test_sql_rejects_unsafe(tmp_path, monkeypatch):
    _seed_project(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="disallowed"):
        run_sql("sql-proj", "ATTACH DATABASE 'x' AS y")
