#!/usr/bin/env python3
"""Copy local workspace/.index.sqlite + files into Supabase."""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select  # noqa: E402

from server import cloud_files, storage  # noqa: E402
from server.models import (  # noqa: E402
    Organization,
    ProjectDiagram,
    ProjectImage,
    ProjectRecord,
    User,
)
from server.settings import get_server_settings  # noqa: E402
from server.state import get_engine, init_db  # noqa: E402
from server.workspace import WORKSPACE_ROOT, project_dir  # noqa: E402

LOCAL_DB = WORKSPACE_ROOT / ".index.sqlite"


def _read_sqlite_table(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    cur = conn.execute(f"SELECT * FROM {table}")
    return cur.fetchall()


def _upload_project_tree(project_id: str, src: Path) -> None:
    for rel in ("source.png", "diagram.annotated.json"):
        p = src / rel
        if p.is_file():
            cloud_files.upload_bytes(project_id, rel, p.read_bytes(), _mime(rel))
    sheets_src = src / "sheets"
    if sheets_src.is_dir():
        for p in sheets_src.glob("*.jsonl"):
            cloud_files.upload_bytes(
                project_id,
                f"sheets/{p.name}",
                p.read_bytes(),
                "application/x-ndjson",
            )


def _mime(rel: str) -> str:
    if rel.endswith(".png"):
        return "image/png"
    if rel.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def main() -> int:
    settings = get_server_settings()
    if not settings.database_url:
        print("Set VIOCI_DATABASE_URL in .env before migrating.")
        return 1
    if not LOCAL_DB.exists():
        print(f"No local database at {LOCAL_DB}")
        return 1

    init_db()
    engine = get_engine()
    local = sqlite3.connect(str(LOCAL_DB))
    local.row_factory = sqlite3.Row

    with Session(engine) as session:
        for row in _read_sqlite_table(local, "organization"):
            if session.get(Organization, row["id"]):
                continue
            session.add(
                Organization(
                    id=row["id"],
                    name=row["name"],
                    slug=row["slug"],
                    plan=row["plan"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        for row in _read_sqlite_table(local, "user"):
            if session.get(User, row["id"]):
                continue
            session.add(
                User(
                    id=row["id"],
                    email=row["email"],
                    password_hash=row["password_hash"],
                    full_name=row["full_name"],
                    job_title=row["job_title"],
                    role=row["role"],
                    organization_id=row["organization_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        for row in _read_sqlite_table(local, "project"):
            if session.get(ProjectRecord, row["id"]):
                continue
            session.add(
                ProjectRecord(
                    id=row["id"],
                    name=row["name"],
                    owner_id=row["owner_id"],
                    organization_id=row["organization_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    parse_status=row["parse_status"],
                    parse_error=row["parse_error"],
                    last_provider=row["last_provider"],
                    last_domain=row["last_domain"],
                    handdrawn=bool(row["handdrawn"]),
                )
            )
        session.commit()

        for row in _read_sqlite_table(local, "project_image"):
            pid = row["project_id"]
            if session.get(ProjectImage, pid):
                continue
            storage.save_image(session, pid, row["data"], row["mime_type"])

        for row in _read_sqlite_table(local, "project_diagram"):
            pid = row["project_id"]
            if session.get(ProjectDiagram, pid):
                continue
            payload = json.loads(row["json_text"])
            storage.save_diagram_json(session, pid, payload)

        if cloud_files.cloud_storage_enabled():
            print("Uploading project files to Storage…")
            for rec in session.exec(select(ProjectRecord)).all():
                src = WORKSPACE_ROOT / rec.id
                if src.is_dir():
                    _upload_project_tree(rec.id, src)
                else:
                    d = project_dir(rec.id)
                    if d.exists():
                        _upload_project_tree(rec.id, d)
        else:
            print("Storage not configured — skipped file upload.")

    local.close()
    print("Migration finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
