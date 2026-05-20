"""Authorization helpers for schema explorer folders."""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, or_, select

from server.models import SchemaFolder, User


def _folder_visible(user: User, rec: SchemaFolder) -> bool:
    if rec.owner_id == user.id:
        return True
    if user.organization_id and rec.organization_id == user.organization_id:
        return True
    return False


def get_accessible_folder(session: Session, user: User, folder_id: str) -> SchemaFolder:
    rec = session.get(SchemaFolder, folder_id)
    if not rec or not _folder_visible(user, rec):
        raise HTTPException(404, "folder not found")
    return rec


def list_accessible_folders(session: Session, user: User) -> list[SchemaFolder]:
    if user.organization_id:
        stmt = select(SchemaFolder).where(
            or_(
                SchemaFolder.owner_id == user.id,
                SchemaFolder.organization_id == user.organization_id,
            )
        )
    else:
        stmt = select(SchemaFolder).where(SchemaFolder.owner_id == user.id)
    return list(session.exec(stmt.order_by(SchemaFolder.name)).all())


def validate_parent_folder(session: Session, user: User, parent_id: str | None) -> None:
    if parent_id is None:
        return
    get_accessible_folder(session, user, parent_id)
