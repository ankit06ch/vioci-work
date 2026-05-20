"""In-memory SQL over schema registry tables; sync mutations back to CSV + manifest."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from server.schema_registry import (
    REGISTRY_TABLES,
    load_schema_registry,
    write_registry_files,
)

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_MAX_ROWS = 500_000


def _quote_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"invalid identifier: {name}")
    return f'"{name}"'


def _validate_sql(sql: str) -> str:
    text = sql.strip()
    if not text:
        raise ValueError("empty SQL")
    # Single statement only
    stripped = text.rstrip(";").strip()
    if ";" in stripped:
        raise ValueError("only one SQL statement per request")
    upper = stripped.upper()
    banned = (
        "ATTACH ",
        "DETACH ",
        "PRAGMA ",
        "VACUUM",
        "LOAD ",
        "INSTALL ",
        "CREATE ",
        "DROP ",
        "ALTER ",
        "COPY ",
        "READ_CSV",
        "READ_PARQUET",
        "EXPORT ",
        "IMPORT ",
        "EXEC ",
        "EXECUTE ",
        "PREPARE ",
        "TRIGGER ",
    )
    for token in banned:
        if token in upper:
            raise ValueError(f"disallowed SQL: {token.strip().lower()}")
    first = upper.split(None, 1)[0] if upper else ""
    if first not in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
        raise ValueError("SQL must be SELECT, INSERT, UPDATE, DELETE, or WITH …")
    return stripped


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f'PRAGMA table_info({_quote_ident(table)})')
    return [str(r[1]) for r in cur.fetchall()]


def _read_table(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[dict[str, Any]]]:
    cols = _table_columns(conn, table)
    if not cols:
        return [], []
    cur = conn.execute(f'SELECT * FROM {_quote_ident(table)}')
    rows = [{c: "" if r[i] is None else r[i] for i, c in enumerate(cols)} for r in cur.fetchall()]
    return cols, rows


def _build_sqlite_conn(doc: dict[str, Any]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    tables = doc.get("tables") or {}
    for tname in REGISTRY_TABLES:
        t = tables.get(tname) or {}
        cols = list(t.get("columns") or [])
        rows = list(t.get("rows") or [])
        if not cols and rows:
            keys: list[str] = []
            seen: set[str] = set()
            for row in rows:
                for k in row:
                    if k not in seen:
                        seen.add(k)
                        keys.append(str(k))
            cols = keys
        if not cols:
            conn.execute(f"CREATE TABLE {_quote_ident(tname)} (placeholder TEXT)")
            continue
        col_defs = ", ".join(f"{_quote_ident(c)} TEXT" for c in cols)
        conn.execute(f"CREATE TABLE {_quote_ident(tname)} ({col_defs})")
        placeholders = ", ".join("?" for _ in cols)
        insert_sql = f"INSERT INTO {_quote_ident(tname)} VALUES ({placeholders})"
        for row in rows:
            conn.execute(
                insert_sql,
                ["" if row.get(c) is None else str(row.get(c, "")) for c in cols],
            )
    return conn


def _sync_conn_to_doc(conn: sqlite3.Connection, doc: dict[str, Any]) -> None:
    from server.schema_registry import _now_iso

    tables = doc.setdefault("tables", {})
    for tname in REGISTRY_TABLES:
        cols, rows = _read_table(conn, tname)
        if cols == ["placeholder"] and not rows:
            cols, rows = [], []
        tables[tname] = {"columns": cols, "rows": rows}
    doc["updated_at"] = _now_iso()


def _save_doc(project_id: str, doc: dict[str, Any]) -> None:
    write_registry_files(project_id, doc)


def get_table_doc(project_id: str, table: str) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    if table not in REGISTRY_TABLES:
        raise ValueError(f"unknown table {table}")
    doc = load_schema_registry(project_id)
    if not doc:
        raise FileNotFoundError("schema registry not found")
    t = (doc.get("tables") or {}).get(table) or {}
    return doc, list(t.get("columns") or []), list(t.get("rows") or [])


def replace_table_rows(
    project_id: str,
    table: str,
    *,
    columns: list[str] | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    doc, existing_cols, _ = get_table_doc(project_id, table)
    cols = columns if columns is not None else existing_cols
    if not cols and rows:
        seen: set[str] = set()
        cols = []
        for row in rows:
            for k in row:
                if k not in seen:
                    seen.add(k)
                    cols.append(str(k))
    doc["tables"][table] = {"columns": cols, "rows": rows}
    from server.schema_registry import _now_iso

    doc["updated_at"] = _now_iso()
    _save_doc(project_id, doc)
    return doc


def update_row(
    project_id: str,
    table: str,
    row_index: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    doc, cols, rows = get_table_doc(project_id, table)
    if row_index < 0 or row_index >= len(rows):
        raise IndexError("row index out of range")
    row = dict(rows[row_index])
    for k, v in values.items():
        if not _IDENT.match(str(k)):
            raise ValueError(f"invalid column {k}")
        row[k] = v
        if k not in cols:
            cols.append(k)
    rows[row_index] = row
    doc["tables"][table] = {"columns": cols, "rows": rows}
    from server.schema_registry import _now_iso

    doc["updated_at"] = _now_iso()
    _save_doc(project_id, doc)
    return {"columns": cols, "rows": rows, "row_index": row_index, "row": row}


def delete_row(project_id: str, table: str, row_index: int) -> dict[str, Any]:
    doc, cols, rows = get_table_doc(project_id, table)
    if row_index < 0 or row_index >= len(rows):
        raise IndexError("row index out of range")
    rows.pop(row_index)
    doc["tables"][table] = {"columns": cols, "rows": rows}
    from server.schema_registry import _now_iso

    doc["updated_at"] = _now_iso()
    _save_doc(project_id, doc)
    return {"columns": cols, "rows": rows, "deleted_index": row_index}


def append_row(project_id: str, table: str, values: dict[str, Any]) -> dict[str, Any]:
    doc, cols, rows = get_table_doc(project_id, table)
    row: dict[str, Any] = {c: "" for c in cols}
    for k, v in values.items():
        if not _IDENT.match(str(k)):
            raise ValueError(f"invalid column {k}")
        row[k] = v
        if k not in cols:
            cols.append(k)
    rows.append(row)
    doc["tables"][table] = {"columns": cols, "rows": rows}
    from server.schema_registry import _now_iso

    doc["updated_at"] = _now_iso()
    _save_doc(project_id, doc)
    return {"columns": cols, "rows": rows, "row_index": len(rows) - 1, "row": row}


def run_sql(project_id: str, sql: str) -> dict[str, Any]:
    doc = load_schema_registry(project_id)
    if not doc:
        raise FileNotFoundError("schema registry not found")
    statement = _validate_sql(sql)
    conn = _build_sqlite_conn(doc)
    try:
        cur = conn.execute(statement)
        if cur.description:
            cols = [d[0] for d in cur.description]
            raw = cur.fetchall()
            if len(raw) > _MAX_ROWS:
                raise ValueError(f"result exceeds {_MAX_ROWS} rows; add LIMIT")
            rows = [{cols[i]: "" if r[i] is None else r[i] for i in range(len(cols))} for r in raw]
            return {
                "columns": cols,
                "rows": rows,
                "row_count": len(rows),
                "mutated": False,
            }
        conn.commit()
        _sync_conn_to_doc(conn, doc)
        _save_doc(project_id, doc)
        return {
            "columns": [],
            "rows": [],
            "row_count": int(cur.rowcount),
            "mutated": True,
            "message": "Changes written to CSV files on disk",
        }
    finally:
        conn.close()
