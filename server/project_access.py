"""Authorization helpers for project-scoped routes."""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, or_, select

from server.models import ProjectRecord, User


def get_accessible_project(session: Session, user: User, project_id: str) -> ProjectRecord:
    rec = session.get(ProjectRecord, project_id)
    if not rec:
        raise HTTPException(404, "project not found")
    if rec.owner_id == user.id:
        return rec
    if user.organization_id and rec.organization_id == user.organization_id:
        return rec
    raise HTTPException(403, "not allowed to access this project")


def list_accessible_projects(session: Session, user: User) -> list[ProjectRecord]:
    if user.organization_id:
        stmt = select(ProjectRecord).where(
            or_(
                ProjectRecord.owner_id == user.id,
                ProjectRecord.organization_id == user.organization_id,
            )
        )
    else:
        stmt = select(ProjectRecord).where(ProjectRecord.owner_id == user.id)
    return list(session.exec(stmt.order_by(ProjectRecord.created_at.desc())).all())
