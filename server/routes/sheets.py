from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from schemagraph.instruments.sheets import SheetMissingError, SheetStore, sheet_id_for
from server.auth import get_current_user
from server.deps import SessionDep
from server.models import User
from server.project_access import get_accessible_project
from server import storage
from server.workspace import sheet_store_root

router = APIRouter(prefix="/projects", tags=["sheets"])


def _node_sheet_id(session, project_id: str, node_id: str) -> str:
    d = storage.get_diagram(session, project_id)
    if not d:
        raise HTTPException(404, "diagram not found")
    for n in d.nodes:
        if n.id == node_id:
            sid = n.properties.get("sheet_id") if n.properties else None
            if isinstance(sid, str):
                return sid
            return sheet_id_for("node", node_id)
    raise HTTPException(404, "node not found")


@router.post("/{project_id}/sheets/{node_id}/upload")
async def upload_sheet(
    project_id: str,
    node_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),  # noqa: B008
):
    get_accessible_project(session, user, project_id)
    sheet_id = _node_sheet_id(session, project_id, node_id)
    root = sheet_store_root(project_id)
    store = SheetStore(root)
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    tmp = root / f"_upload_{node_id}.csv"
    tmp.write_bytes(raw)
    try:
        n = store.attach_csv(sheet_id, tmp)
    finally:
        tmp.unlink(missing_ok=True)
    from server.workspace import after_sheet_write

    after_sheet_write(project_id, root / "sheets" / f"{sheet_id}.jsonl")
    return {"sheet_id": sheet_id, "rows_written": n}


@router.get("/{project_id}/sheets/{node_id}/rows")
def sheet_rows(
    project_id: str,
    node_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
    where: str | None = None,
    limit: int = 100,
):
    get_accessible_project(session, user, project_id)
    sheet_id = _node_sheet_id(session, project_id, node_id)
    store = SheetStore(sheet_store_root(project_id))
    try:
        rows = store.query(sheet_id, where=where, limit=limit)
    except SheetMissingError:
        return {"sheet_id": sheet_id, "rows": [], "count": 0}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"sheet_id": sheet_id, "rows": rows, "count": len(rows)}


@router.get("/{project_id}/sheets/{node_id}/summary")
def sheet_summary(
    project_id: str,
    node_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    sheet_id = _node_sheet_id(session, project_id, node_id)
    store = SheetStore(sheet_store_root(project_id))
    s = store.summary(sheet_id)
    return json.loads(json.dumps(s.__dict__, default=str))
