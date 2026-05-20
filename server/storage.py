"""Persist project images and diagram IR in SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from schemagraph.ir.schema import Diagram
from server.models import ProjectDiagram, ProjectImage
from server.workspace import diagram_path, image_path, read_diagram, write_diagram


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
