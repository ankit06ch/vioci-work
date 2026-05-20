"""Build queryable satellite schema tables from diagram IR, annotations, and project metadata."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from server import storage
from server.annotation_service import load_document
from server.models import ProjectRecord
from server.workspace import project_dir

SCHEMA_VERSION = 1
SCHEMA_DIR_NAME = "schema"
MANIFEST_NAME = "satellite_schema.json"
REGISTRY_TABLES = frozenset({"components", "dependencies", "properties"})


def schema_dir(project_id: str) -> Path:
    d = project_dir(project_id) / SCHEMA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifest_path(project_id: str) -> Path:
    return schema_dir(project_id) / MANIFEST_NAME


def registry_exists(project_id: str) -> bool:
    return manifest_path(project_id).is_file()


def list_registry_files(project_id: str) -> list[dict[str, Any]]:
    """Manifest + CSV paths for schematic explorer."""
    doc = load_schema_registry(project_id)
    if not doc:
        return []
    out: list[dict[str, Any]] = []
    manifest = manifest_path(project_id)
    if manifest.is_file():
        out.append(
            {
                "id": "manifest",
                "name": MANIFEST_NAME,
                "path": f"schema/{MANIFEST_NAME}",
                "size_bytes": manifest.stat().st_size,
            }
        )
    for key, rel in (doc.get("files") or {}).items():
        p = project_dir(project_id) / str(rel)
        if p.is_file():
            out.append(
                {
                    "id": key,
                    "name": p.name,
                    "path": str(rel),
                    "size_bytes": p.stat().st_size,
                }
            )
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_prop(value: Any) -> tuple[str, str, str]:
    if value is None:
        return "", "", ""
    if isinstance(value, dict):
        if "value" in value:
            unit = value.get("unit")
            raw = value.get("raw")
            return str(value["value"]), str(unit or ""), str(raw or "")
        return json.dumps(value, ensure_ascii=False), "", ""
    if isinstance(value, bool):
        return str(value).lower(), "", ""
    return str(value), "", ""


def _node_index(diagram: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not diagram:
        return {}
    return {
        str(n["id"]): n
        for n in diagram.get("nodes") or []
        if isinstance(n, dict) and n.get("id")
    }


def _ann_by_node(annotations: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for a in annotations:
        if not isinstance(a, dict):
            continue
        nid = a.get("node_id")
        if nid:
            out[str(nid)] = a
    return out


def _part_row(
    ann: dict[str, Any] | None,
    node: dict[str, Any] | None,
) -> dict[str, Any]:
    name = (ann or {}).get("name") or (node or {}).get("label") or ""
    row: dict[str, Any] = {
        "part_id": (ann or {}).get("id") or "",
        "node_id": (ann or {}).get("node_id") or (node or {}).get("id") or "",
        "name": name,
        "kind": (node or {}).get("kind") or "",
        "domain": (ann or {}).get("domain") or (node or {}).get("domain") or "",
        "label": (node or {}).get("label") or name,
        "mass_kg": (ann or {}).get("mass_kg"),
        "length_m": (ann or {}).get("length_m"),
        "width_m": (ann or {}).get("width_m"),
        "height_m": (ann or {}).get("height_m"),
        "depth_m": (ann or {}).get("depth_m"),
        "volume_m3": (ann or {}).get("volume_m3"),
        "power_w": (ann or {}).get("power_w"),
        "material": (ann or {}).get("material"),
        "notes": (ann or {}).get("notes"),
        "auto_detected": (ann or {}).get("auto_detected"),
        "node_confidence": (node or {}).get("confidence"),
    }
    extra = (ann or {}).get("extra") if ann else None
    if isinstance(extra, dict):
        for dp in extra.get("dataPoints") or []:
            if not isinstance(dp, dict):
                continue
            label = str(dp.get("label") or "").strip()
            if not label:
                continue
            key = f"custom_{label.lower().replace(' ', '_')}"
            row[key] = dp.get("value")
    return row


def _component_columns(rows: list[dict[str, Any]]) -> list[str]:
    base = [
        "part_id",
        "node_id",
        "name",
        "kind",
        "domain",
        "label",
        "mass_kg",
        "length_m",
        "width_m",
        "height_m",
        "depth_m",
        "volume_m3",
        "power_w",
        "material",
        "notes",
        "auto_detected",
        "node_confidence",
    ]
    extra_keys: list[str] = []
    seen = set(base)
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                extra_keys.append(k)
    return base + sorted(extra_keys)


def build_tables(
    *,
    project_id: str,
    project_name: str,
    parse_status: str,
    last_domain: str | None,
    diagram: dict[str, Any] | None,
    annotations: list[Any],
) -> dict[str, Any]:
    nodes = _node_index(diagram)
    ann_map = _ann_by_node(annotations)
    used_nodes: set[str] = set()

    component_rows: list[dict[str, Any]] = []
    for nid, node in nodes.items():
        used_nodes.add(nid)
        component_rows.append(_part_row(ann_map.get(nid), node))
    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        nid = ann.get("node_id")
        if nid and str(nid) in used_nodes:
            continue
        component_rows.append(_part_row(ann, None))

    component_rows.sort(key=lambda r: (str(r.get("name") or "").lower(), str(r.get("node_id") or "")))

    name_by_id: dict[str, str] = {}
    for r in component_rows:
        nid = str(r.get("node_id") or "")
        if nid:
            name_by_id[nid] = str(r.get("name") or nid)

    dep_rows: list[dict[str, Any]] = []
    for edge in (diagram or {}).get("edges") or []:
        if not isinstance(edge, dict):
            continue
        eid = str(edge.get("id") or "")
        src = str(edge.get("source") or "")
        tgt = str(edge.get("target") or "")
        dep_rows.append(
            {
                "edge_id": eid,
                "source_id": src,
                "source_name": name_by_id.get(src, src),
                "target_id": tgt,
                "target_name": name_by_id.get(tgt, tgt),
                "kind": edge.get("kind") or "",
                "label": edge.get("label") or "",
                "directed": edge.get("directed"),
                "domain": edge.get("domain") or "",
                "confidence": edge.get("confidence"),
            }
        )
    dep_rows.sort(key=lambda r: (str(r.get("source_name") or ""), str(r.get("target_name") or "")))

    prop_rows: list[dict[str, Any]] = []
    for nid, node in nodes.items():
        label = name_by_id.get(nid, nid)
        for key, val in (node.get("properties") or {}).items():
            v, unit, raw = _serialize_prop(val)
            prop_rows.append(
                {
                    "entity_type": "component",
                    "entity_id": nid,
                    "entity_name": label,
                    "property_key": str(key),
                    "value": v,
                    "unit": unit,
                    "raw": raw,
                }
            )
    for edge in (diagram or {}).get("edges") or []:
        if not isinstance(edge, dict):
            continue
        eid = str(edge.get("id") or "")
        for key, val in (edge.get("properties") or {}).items():
            v, unit, raw = _serialize_prop(val)
            prop_rows.append(
                {
                    "entity_type": "dependency",
                    "entity_id": eid,
                    "entity_name": edge.get("label") or eid,
                    "property_key": str(key),
                    "value": v,
                    "unit": unit,
                    "raw": raw,
                }
            )
    for r in component_rows:
        pid = str(r.get("part_id") or r.get("node_id") or "")
        pname = str(r.get("name") or "")
        for key in (
            "mass_kg",
            "length_m",
            "width_m",
            "height_m",
            "depth_m",
            "volume_m3",
            "power_w",
            "material",
            "notes",
        ):
            val = r.get(key)
            if val is None or val == "":
                continue
            prop_rows.append(
                {
                    "entity_type": "component",
                    "entity_id": pid or pname,
                    "entity_name": pname,
                    "property_key": key,
                    "value": str(val),
                    "unit": "",
                    "raw": "",
                }
            )

    prop_rows.sort(
        key=lambda r: (
            str(r.get("entity_type") or ""),
            str(r.get("entity_name") or "").lower(),
            str(r.get("property_key") or ""),
        )
    )

    comp_cols = _component_columns(component_rows)
    dep_cols = [
        "edge_id",
        "source_id",
        "source_name",
        "target_id",
        "target_name",
        "kind",
        "label",
        "directed",
        "domain",
        "confidence",
    ]
    prop_cols = [
        "entity_type",
        "entity_id",
        "entity_name",
        "property_key",
        "value",
        "unit",
        "raw",
    ]

    return {
        "version": SCHEMA_VERSION,
        "project_id": project_id,
        "project_name": project_name,
        "updated_at": _now_iso(),
        "parse_status": parse_status,
        "last_domain": last_domain,
        "node_count": len(nodes),
        "edge_count": len(dep_rows),
        "part_count": len(component_rows),
        "tables": {
            "components": {"columns": comp_cols, "rows": component_rows},
            "dependencies": {"columns": dep_cols, "rows": dep_rows},
            "properties": {"columns": prop_cols, "rows": prop_rows},
        },
        "files": {
            "components": "schema/components.csv",
            "dependencies": "schema/dependencies.csv",
            "properties": "schema/properties.csv",
        },
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in columns})


def write_registry_files(project_id: str, doc: dict[str, Any]) -> None:
    root = schema_dir(project_id)
    tables = doc.get("tables") or {}
    files = doc.get("files") or {}
    for key, rel in files.items():
        table = tables.get(key) or {}
        cols = table.get("columns") or []
        rows = table.get("rows") or []
        _write_csv(project_dir(project_id) / str(rel), cols, rows)
    manifest_path(project_id).write_text(
        json.dumps(doc, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    from server.workspace import after_registry_write

    after_registry_write(project_id)


def init_schema_registry(
    session: Session,
    project_id: str,
    *,
    project_name: str | None = None,
    parse_status: str = "idle",
) -> dict[str, Any]:
    """Create empty schema files when a schematic is uploaded (before IR parse)."""
    rec = session.get(ProjectRecord, project_id)
    name = project_name or (rec.name if rec else project_id)
    status = parse_status or (rec.parse_status if rec else "idle")
    doc = build_tables(
        project_id=project_id,
        project_name=name,
        parse_status=status,
        last_domain=rec.last_domain if rec else None,
        diagram=None,
        annotations=[],
    )
    doc["tables"]["components"]["rows"] = [
        {
            "part_id": "",
            "node_id": "",
            "name": "(awaiting parse)",
            "kind": "",
            "domain": "",
            "label": "Upload received — run parse to populate dependency graph and components",
        }
    ]
    write_registry_files(project_id, doc)
    return doc


def rebuild_schema_registry(session: Session, project_id: str) -> dict[str, Any]:
    rec = session.get(ProjectRecord, project_id)
    if not rec:
        raise ValueError(f"unknown project {project_id}")
    diagram = storage.get_diagram_dict(session, project_id)
    ann_doc = load_document(session, project_id)
    annotations = [a.model_dump(mode="json") for a in ann_doc.annotations]
    doc = build_tables(
        project_id=project_id,
        project_name=rec.name,
        parse_status=rec.parse_status,
        last_domain=rec.last_domain,
        diagram=diagram,
        annotations=annotations,
    )
    write_registry_files(project_id, doc)
    return doc


def load_schema_registry(project_id: str) -> dict[str, Any] | None:
    p = manifest_path(project_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def query_registry(
    doc: dict[str, Any],
    table: str,
    *,
    q: str | None = None,
    limit: int | None = 5000,
) -> dict[str, Any]:
    tables = doc.get("tables") or {}
    t = tables.get(table)
    if not t:
        return {"columns": [], "rows": [], "total": 0, "filtered": 0}
    columns = list(t.get("columns") or [])
    rows = list(t.get("rows") or [])
    total = len(rows)
    if q:
        needle = q.strip().lower()
        if needle:
            filtered: list[dict[str, Any]] = []
            for row in rows:
                hay = " ".join(str(row.get(c, "")) for c in columns).lower()
                if needle in hay:
                    filtered.append(row)
            rows = filtered
    filtered_count = len(rows)
    truncated = False
    if limit is not None and len(rows) > limit:
        rows = rows[:limit]
        truncated = True
    return {
        "columns": columns,
        "rows": rows,
        "total": total,
        "filtered": filtered_count,
        "truncated": truncated,
    }


def registry_csv_bytes(project_id: str, table: str) -> bytes | None:
    doc = load_schema_registry(project_id)
    if not doc:
        return None
    rel = (doc.get("files") or {}).get(table)
    if not rel:
        return None
    p = project_dir(project_id) / str(rel)
    if not p.is_file():
        return None
    return p.read_bytes()


def registry_csv_text(project_id: str, table: str) -> str:
    data = registry_csv_bytes(project_id, table)
    return data.decode("utf-8") if data else ""
