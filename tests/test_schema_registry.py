from __future__ import annotations

from server.schema_registry import build_tables, query_registry, write_registry_files
from server.workspace import project_dir


def test_build_tables_merges_diagram_and_annotations(tmp_path, monkeypatch):
    pid = "test-proj-1"
    monkeypatch.setattr("server.schema_registry.project_dir", lambda x: tmp_path / x)
    monkeypatch.setattr("server.workspace.project_dir", lambda x: tmp_path / x)
    monkeypatch.setattr("server.workspace.ensure_workspace", lambda: tmp_path)
    monkeypatch.setattr("server.workspace._use_cloud_files", lambda: False)

    diagram = {
        "nodes": [
            {"id": "n1", "label": "Battery", "kind": "storage", "domain": "power"},
            {"id": "n2", "label": "Solar", "kind": "source", "domain": "power"},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n2",
                "target": "n1",
                "kind": "power",
                "label": "charges",
                "directed": True,
            }
        ],
    }
    annotations = [
        {
            "id": "a1",
            "node_id": "n1",
            "name": "Main battery",
            "mass_kg": 12.5,
            "auto_detected": True,
        }
    ]
    doc = build_tables(
        project_id=pid,
        project_name="Demo SAT",
        parse_status="done",
        last_domain="spacecraft",
        diagram=diagram,
        annotations=annotations,
    )
    assert doc["node_count"] == 2
    assert doc["edge_count"] == 1
    comps = doc["tables"]["components"]["rows"]
    assert any(r["node_id"] == "n1" and r["mass_kg"] == 12.5 for r in comps)
    deps = doc["tables"]["dependencies"]["rows"]
    assert deps[0]["source_name"] == "Solar"
    assert deps[0]["target_name"] == "Main battery"

    write_registry_files(pid, doc)
    root = project_dir(pid)
    assert (root / "schema" / "satellite_schema.json").is_file()
    assert (root / "schema" / "components.csv").is_file()
    assert (root / "schema" / "dependencies.csv").is_file()

    q = query_registry(doc, "dependencies", q="solar")
    assert q["filtered"] == 1
    assert q["rows"][0]["source_id"] == "n2"


def test_init_placeholder_row():
    doc = build_tables(
        project_id="x",
        project_name="upload.png",
        parse_status="idle",
        last_domain=None,
        diagram=None,
        annotations=[],
    )
    assert doc["tables"]["components"]["rows"] == []
