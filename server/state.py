"""Database engine and schema initialization."""

from __future__ import annotations

import sqlite3

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine

from server.models import (
    Organization,
    ProjectAnnotations,
    ProjectDiagram,
    ProjectImage,
    ProjectRecord,
    SchemaFolder,
    User,
)
from server.settings import get_server_settings
from server.workspace import ensure_workspace, index_db_path

_engine = None

# Re-export models for backward-compatible imports
__all__ = [
    "ProjectRecord",
    "Organization",
    "User",
    "ProjectImage",
    "ProjectDiagram",
    "SchemaFolder",
    "init_db",
    "get_engine",
]


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _migrate_legacy_project_table(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(project)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    if "owner_id" not in cols:
        conn.execute("ALTER TABLE project ADD COLUMN owner_id TEXT")
    if "organization_id" not in cols:
        conn.execute("ALTER TABLE project ADD COLUMN organization_id TEXT")
    if "folder_id" not in cols:
        conn.execute("ALTER TABLE project ADD COLUMN folder_id TEXT")
    conn.commit()


def _migrate_project_columns(engine) -> None:
    """Add columns introduced after first deploy (SQLite + Postgres)."""
    insp = inspect(engine)
    if "project" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("project")}
    stmts: list[str] = []
    if "owner_id" not in cols:
        stmts.append("ALTER TABLE project ADD COLUMN owner_id VARCHAR")
    if "organization_id" not in cols:
        stmts.append("ALTER TABLE project ADD COLUMN organization_id VARCHAR")
    if "folder_id" not in cols:
        stmts.append("ALTER TABLE project ADD COLUMN folder_id VARCHAR")
    if "image_enhanced" not in cols:
        bool_default = "FALSE" if engine.dialect.name == "postgresql" else "0"
        stmts.append(f"ALTER TABLE project ADD COLUMN image_enhanced BOOLEAN DEFAULT {bool_default}")
    if "image_quality_score" not in cols:
        stmts.append("ALTER TABLE project ADD COLUMN image_quality_score FLOAT")
    if not stmts:
        return
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))


def init_db() -> None:
    global _engine
    ensure_workspace()
    settings = get_server_settings()
    if settings.database_url:
        url = _normalize_database_url(settings.database_url)
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 20},
        )
    else:
        db_path = index_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
    SQLModel.metadata.create_all(_engine)
    _migrate_project_columns(_engine)
    if not settings.database_url:
        raw = sqlite3.connect(str(index_db_path()))
        try:
            _migrate_legacy_project_table(raw)
        finally:
            raw.close()


def get_engine():
    if _engine is None:
        init_db()
    return _engine
