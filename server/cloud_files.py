"""Sync project files to Supabase Storage (free tier) with a local cache."""

from __future__ import annotations

import logging
from pathlib import Path

from server.settings import get_server_settings

log = logging.getLogger(__name__)

_client = None


def cloud_storage_enabled() -> bool:
    s = get_server_settings()
    return bool(s.supabase_url and s.supabase_service_role_key)


def _client():
    global _client
    if _client is not None:
        return _client
    s = get_server_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise RuntimeError("Supabase Storage is not configured")
    try:
        from supabase import create_client
    except ImportError as e:
        raise RuntimeError(
            "Install cloud extras: pip install -e '.[web,cloud]'"
        ) from e
    _client = create_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def _bucket():
    return get_server_settings().supabase_bucket


def _object_key(project_id: str, relative: str) -> str:
    rel = relative.lstrip("/")
    return f"{project_id}/{rel}"


def upload_file(project_id: str, local_path: Path, relative: str | None = None) -> None:
    if not cloud_storage_enabled() or not local_path.is_file():
        return
    rel = relative or local_path.name
    key = _object_key(project_id, rel)
    data = local_path.read_bytes()
    mime = "application/octet-stream"
    if local_path.suffix.lower() == ".png":
        mime = "image/png"
    elif local_path.suffix.lower() == ".json":
        mime = "application/json"
    elif local_path.suffix.lower() == ".jsonl":
        mime = "application/x-ndjson"
    try:
        _client().storage.from_(_bucket()).upload(
            key,
            data,
            file_options={"content-type": mime, "upsert": "true"},
        )
    except Exception as e:
        log.warning("upload %s failed: %s", key, e)


def upload_bytes(project_id: str, relative: str, data: bytes, content_type: str) -> None:
    if not cloud_storage_enabled():
        return
    key = _object_key(project_id, relative)
    try:
        _client().storage.from_(_bucket()).upload(
            key,
            data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        log.warning("upload %s failed: %s", key, e)


def download_file(project_id: str, relative: str, dest: Path) -> bool:
    if not cloud_storage_enabled():
        return False
    key = _object_key(project_id, relative)
    try:
        data = _client().storage.from_(_bucket()).download(key)
    except Exception:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def sync_project_from_cloud(project_dir: Path, project_id: str) -> None:
    """Pull known project artifacts from Storage into the local cache."""
    if not cloud_storage_enabled():
        return
    project_dir.mkdir(parents=True, exist_ok=True)
    for rel in ("source.png", "diagram.annotated.json"):
        dest = project_dir / rel
        if not dest.exists():
            download_file(project_id, rel, dest)
    try:
        sheet_entries = _client().storage.from_(_bucket()).list(f"{project_id}/sheets")
    except Exception:
        sheet_entries = []
    sheets_dir = project_dir / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    for item in sheet_entries or []:
        name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
        if not name or not name.endswith(".jsonl"):
            continue
        dest = sheets_dir / name
        if not dest.exists():
            download_file(project_id, f"sheets/{name}", dest)


def delete_project_cloud(project_id: str) -> None:
    if not cloud_storage_enabled():
        return
    bucket = _client().storage.from_(_bucket())
    for rel in ("source.png", "diagram.annotated.json"):
        try:
            bucket.remove([_object_key(project_id, rel)])
        except Exception as e:
            log.debug("remove %s: %s", rel, e)
    try:
        for item in bucket.list(f"{project_id}/sheets") or []:
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if name:
                bucket.remove([_object_key(project_id, f"sheets/{name}")])
    except Exception as e:
        log.debug("remove sheets for %s: %s", project_id, e)
