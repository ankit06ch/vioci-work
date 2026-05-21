"""Persist project images and diagram IR in SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from schemagraph.ir.schema import Diagram
from server.models import ProjectDiagram, ProjectImage
from server.workspace import (
    WORKSPACE_ROOT,
    diagram_path,
    image_path,
    original_image_path,
    read_diagram,
    write_diagram,
)


def backup_original_image(project_id: str, data: bytes) -> None:
    """Keep first-upload bytes so users can restore after a bad enhance."""
    p = original_image_path(project_id)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    from server.workspace import after_original_image_write

    after_original_image_write(project_id)


def get_original_image_bytes(project_id: str) -> bytes | None:
    p = original_image_path(project_id)
    if p.exists():
        return p.read_bytes()
    return None


def _image_has_content(png_bytes: bytes) -> bool:
    import io

    import numpy as np
    from PIL import Image

    arr = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
    return float(arr.std()) >= 35


def _find_restorable_bytes(project_id: str) -> bytes | None:
    for candidate in (
        get_original_image_bytes(project_id),
        _read_if_content(image_path(project_id)),
        _read_if_content(WORKSPACE_ROOT / project_id / "source.png"),
    ):
        if candidate is not None:
            return candidate
    return None


def _read_if_content(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return raw if _image_has_content(raw) else None


def restore_original_image(session: Session, project_id: str) -> bool:
    """Restore schematic from backup, cache, or repo workspace copy."""
    raw = _find_restorable_bytes(project_id)
    if raw is None:
        return False
    backup_original_image(project_id, raw)
    save_image(session, project_id, raw, "image/png")
    return True


def save_image(session: Session, project_id: str, data: bytes, mime_type: str = "image/png") -> None:
    row = session.get(ProjectImage, project_id)
    now = datetime.now(timezone.utc)
    if row:
        row.data = data
        row.mime_type = mime_type
        row.updated_at = now
        session.add(row)
    else:
        session.add(ProjectImage(project_id=project_id, data=data, mime_type=mime_type, updated_at=now))
    # Keep filesystem copy for sheet store paths
    p = image_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    from server.workspace import after_image_write

    after_image_write(project_id)
    session.commit()


def get_image(session: Session, project_id: str) -> tuple[bytes, str] | None:
    row = session.get(ProjectImage, project_id)
    if row:
        return row.data, row.mime_type
    p = image_path(project_id)
    if p.exists():
        return p.read_bytes(), "image/png"
    return None


def ensure_source_image_file(session: Session, project_id: str) -> Path:
    """Write source.png to the workspace cache when only Postgres/Storage has the bytes.

    On Render (and other ephemeral hosts) ``/root/.cache/vioci/...`` is empty after
    restarts while ``project_images`` still holds the upload. Parse/CV require a path.
    """
    p = image_path(project_id)
    if _read_if_content(p) is not None:
        return p

    row = session.get(ProjectImage, project_id)
    if row and row.data:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(row.data)
        from server.workspace import after_image_write

        after_image_write(project_id)
        return p

    if p.is_file() and p.stat().st_size > 0:
        return p

    raise FileNotFoundError(
        f"Source image missing for project {project_id}. Re-upload the schematic."
    )


def save_diagram_json(session: Session, project_id: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2)
    row = session.get(ProjectDiagram, project_id)
    now = datetime.now(timezone.utc)
    if row:
        row.json_text = text
        row.updated_at = now
        session.add(row)
    else:
        session.add(ProjectDiagram(project_id=project_id, json_text=text, updated_at=now))
    session.commit()
    write_diagram(project_id, Diagram.model_validate(payload))


def get_diagram_dict(session: Session, project_id: str) -> dict[str, Any] | None:
    row = session.get(ProjectDiagram, project_id)
    if row:
        return json.loads(row.json_text)
    return None


def get_diagram(session: Session, project_id: str) -> Diagram | None:
    d = get_diagram_dict(session, project_id)
    if d is not None:
        return Diagram.model_validate(d)
    return read_diagram(project_id)


def has_diagram(session: Session, project_id: str) -> bool:
    if session.get(ProjectDiagram, project_id):
        return True
    return diagram_path(project_id).exists()


def delete_blobs(session: Session, project_id: str) -> None:
    from server.models import ProjectAnnotations

    img = session.get(ProjectImage, project_id)
    if img:
        session.delete(img)
    diag = session.get(ProjectDiagram, project_id)
    if diag:
        session.delete(diag)
    ann = session.get(ProjectAnnotations, project_id)
    if ann:
        session.delete(ann)
    session.commit()
