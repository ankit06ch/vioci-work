from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from server.auth import get_current_user
from server.deps import SessionDep
from server.folder_access import get_accessible_folder, list_accessible_folders, validate_parent_folder
from server.models import ProjectRecord, SchemaFolder, User
from server.schemas import SchemaFolderCreate, SchemaFolderOut

router = APIRouter(prefix="/folders", tags=["folders"])


def _to_out(rec: SchemaFolder) -> SchemaFolderOut:
    return SchemaFolderOut(
        id=rec.id,
        name=rec.name,
        parent_id=rec.parent_id,
        created_at=rec.created_at,
    )


@router.get("", response_model=list[SchemaFolderOut])
def list_folders(session: SessionDep, user: User = Depends(get_current_user)):
    return [_to_out(f) for f in list_accessible_folders(session, user)]


@router.post("", response_model=SchemaFolderOut)
def create_folder(body: SchemaFolderCreate, session: SessionDep, user: User = Depends(get_current_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "folder name required")
    validate_parent_folder(session, user, body.parent_id)

    existing = session.exec(
        select(SchemaFolder).where(
            SchemaFolder.owner_id == user.id,
            SchemaFolder.parent_id == body.parent_id,
            SchemaFolder.name == name,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"folder '{name}' already exists here")

    rec = SchemaFolder(
        id=str(uuid.uuid4()),
        name=name,
        parent_id=body.parent_id,
        owner_id=user.id,
        organization_id=user.organization_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _to_out(rec)


@router.delete("/{folder_id}", status_code=204)
def delete_folder(folder_id: str, session: SessionDep, user: User = Depends(get_current_user)):
    rec = get_accessible_folder(session, user, folder_id)
    child = session.exec(select(SchemaFolder).where(SchemaFolder.parent_id == folder_id)).first()
    if child:
        raise HTTPException(400, "folder is not empty (contains subfolders)")
    proj = session.exec(select(ProjectRecord).where(ProjectRecord.folder_id == folder_id)).first()
    if proj:
        raise HTTPException(400, "folder is not empty (contains schematics)")
    session.delete(rec)
    session.commit()
