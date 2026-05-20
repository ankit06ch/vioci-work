"""Filesystem layout for project artifacts (local cache; optional Supabase sync)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from schemagraph.ir.schema import Diagram

from server import cloud_files
from server.settings import get_server_settings

_REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = _REPO_ROOT / "workspace"
INDEX_DB = WORKSPACE_ROOT / ".index.sqlite"


def _use_cloud_files() -> bool:
    return cloud_files.cloud_storage_enabled()


def _local_workspace_root() -> Path:
    if _use_cloud_files():
        return get_server_settings().file_cache_dir
    return WORKSPACE_ROOT


def index_db_path() -> Path:
    s = get_server_settings()
    if s.sqlite_path is not None:
        return s.sqlite_path
    if s.database_url:
        return WORKSPACE_ROOT / ".index.sqlite"  # unused when Postgres is configured
    return INDEX_DB


def ensure_workspace() -> Path:
    root = _local_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    if not _use_cloud_files():
        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return root


def project_dir(project_id: str) -> Path:
    d = ensure_workspace() / project_id
    if _use_cloud_files():
        cloud_files.sync_project_from_cloud(d, project_id)
    return d


def image_path(project_id: str) -> Path:
    return project_dir(project_id) / "source.png"


def original_image_path(project_id: str) -> Path:
    return project_dir(project_id) / "source.original.png"


def diagram_path(project_id: str) -> Path:
    return project_dir(project_id) / "diagram.annotated.json"


def sheet_store_root(project_id: str) -> Path:
    d = project_dir(project_id)
    (d / "sheets").mkdir(parents=True, exist_ok=True)
    return d


def write_diagram(project_id: str, diagram: Diagram) -> None:
    p = diagram_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = diagram.model_dump(mode="json")
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if _use_cloud_files():
        cloud_files.upload_file(project_id, p)


def read_diagram(project_id: str) -> Diagram | None:
    p = diagram_path(project_id)
    if not p.exists():
        return None
    return Diagram.model_validate_json(p.read_text(encoding="utf-8"))


def read_diagram_dict(project_id: str) -> dict[str, Any] | None:
    p = diagram_path(project_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def after_image_write(project_id: str) -> None:
    if _use_cloud_files():
        cloud_files.upload_file(project_id, image_path(project_id))


def after_original_image_write(project_id: str) -> None:
    if _use_cloud_files():
        cloud_files.upload_file(project_id, original_image_path(project_id))


def after_sheet_write(project_id: str, sheet_path: Path) -> None:
    if _use_cloud_files() and sheet_path.is_file():
        cloud_files.upload_file(project_id, sheet_path, f"sheets/{sheet_path.name}")


def after_registry_write(project_id: str) -> None:
    """Upload satellite_schema.json and schema/*.csv after local write."""
    if not _use_cloud_files():
        return
    root = project_dir(project_id)
    manifest = root / "schema" / "satellite_schema.json"
    if manifest.is_file():
        cloud_files.upload_file(project_id, manifest, "schema/satellite_schema.json")
    schema_dir = root / "schema"
    if schema_dir.is_dir():
        for p in schema_dir.glob("*.csv"):
            cloud_files.upload_file(project_id, p, f"schema/{p.name}")


def delete_project_files(project_id: str) -> None:
    d = ensure_workspace() / project_id
    cloud_files.delete_project_cloud(project_id)
    if d.exists():
        shutil.rmtree(d)
