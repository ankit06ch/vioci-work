from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from server.auth import get_current_user
from server.deps import SessionDep
from server.models import ProjectRecord, User
from server.folder_access import get_accessible_folder, validate_parent_folder
from server.project_access import get_accessible_project, list_accessible_projects
from server.schemas import DiagramNodeUpdate, DiagramNodesDelete, ProjectFolderMove, ProjectOut, UploadResponse
from server import storage
from server.routes.parse import enqueue_parse
from server.schema_registry import registry_exists, rebuild_schema_registry
from server.workspace import delete_project_files

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_out(session, rec: ProjectRecord) -> ProjectOut:
    return ProjectOut(
        id=rec.id,
        name=rec.name,
        folder_id=rec.folder_id,
        created_at=rec.created_at,
        parse_status=rec.parse_status,
        parse_error=rec.parse_error,
        last_provider=rec.last_provider,
        last_domain=rec.last_domain,
        handdrawn=rec.handdrawn,
        has_diagram=storage.has_diagram(session, rec.id),
        has_schema_registry=registry_exists(rec.id),
        image_enhanced=rec.image_enhanced,
        image_quality_score=rec.image_quality_score,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_projects(
    session: SessionDep,
    user: User = Depends(get_current_user),
    files: list[UploadFile] = File(...),  # noqa: B008
    folder_id: str | None = Form(default=None),
):
    if not files:
        raise HTTPException(400, "no files uploaded")
    validate_parent_folder(session, user, folder_id)
    if folder_id:
        get_accessible_folder(session, user, folder_id)
    created: list[ProjectOut] = []
    for f in files:
        raw = await f.read()
        if not raw:
            continue
        pid = str(uuid.uuid4())
        name = f.filename or "upload"
        lower = name.lower()
        if lower.endswith(".json"):
            raise HTTPException(
                400,
                "Launch readiness JSON cannot create a new project. Open an existing schematic "
                "project and import the file from the Launch tab (Import mission data).",
            )
        mime = f.content_type or "application/octet-stream"
        if lower.endswith(".pdf"):
            mime = "application/pdf"
        else:
            try:
                img = Image.open(io.BytesIO(raw))
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                raw = buf.getvalue()
                mime = "image/png"
            except (OSError, UnidentifiedImageError) as e:
                raise HTTPException(
                    400,
                    f"Unsupported upload '{name}'. Use schematic images (PNG, JPEG, WebP, GIF) or PDF.",
                ) from e

        rec = ProjectRecord(
            id=pid,
            name=name,
            folder_id=folder_id,
            owner_id=user.id,
            organization_id=user.organization_id,
            created_at=datetime.now(timezone.utc),
            parse_status="idle",
        )
        session.add(rec)
        session.commit()
        from server.annotation_schemas import AnnotationsDocument
        from server.annotation_service import save_document
        from server.image_enhance import assess_and_maybe_enhance, assess_quality

        storage.backup_original_image(pid, raw)
        if mime.startswith("image/"):
            score = assess_quality(raw)
            raw, _, enhanced = assess_and_maybe_enhance(raw)
            rec.image_quality_score = assess_quality(raw)
            rec.image_enhanced = enhanced
        else:
            score = None
            enhanced = False
        storage.save_image(session, pid, raw, mime)
        session.add(rec)
        session.commit()
        save_document(
            session,
            pid,
            AnnotationsDocument(
                image_enhanced=enhanced,
                image_quality_score=rec.image_quality_score,
            ),
        )
        from server.schema_registry import init_schema_registry

        init_schema_registry(session, pid, project_name=name)
        enqueue_parse(pid)
        session.refresh(rec)
        created.append(_to_out(session, rec))
    return UploadResponse(projects=created)


@router.get("", response_model=list[ProjectOut])
def list_projects(session: SessionDep, user: User = Depends(get_current_user)):
    rows = list_accessible_projects(session, user)
    return [_to_out(session, r) for r in rows]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, session: SessionDep, user: User = Depends(get_current_user)):
    rec = get_accessible_project(session, user, project_id)
    return _to_out(session, rec)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: SessionDep, user: User = Depends(get_current_user)):
    rec = get_accessible_project(session, user, project_id)
    storage.delete_blobs(session, project_id)
    session.delete(rec)
    session.commit()
    delete_project_files(project_id)


@router.get("/{project_id}/image")
def get_image(project_id: str, session: SessionDep, user: User = Depends(get_current_user)):
    get_accessible_project(session, user, project_id)
    blob = storage.get_image(session, project_id)
    if not blob:
        raise HTTPException(404, "image missing")
    data, mime = blob
    return Response(content=data, media_type=mime)


@router.patch("/{project_id}/folder", response_model=ProjectOut)
def move_project_folder(
    project_id: str,
    body: ProjectFolderMove,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    rec = get_accessible_project(session, user, project_id)
    validate_parent_folder(session, user, body.folder_id)
    if body.folder_id:
        get_accessible_folder(session, user, body.folder_id)
    rec.folder_id = body.folder_id
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _to_out(session, rec)


@router.get("/{project_id}/diagram")
def get_diagram(project_id: str, session: SessionDep, user: User = Depends(get_current_user)):
    get_accessible_project(session, user, project_id)
    data = storage.get_diagram_dict(session, project_id)
    if data is None:
        raise HTTPException(404, "diagram not parsed yet")
    return data


@router.patch("/{project_id}/diagram/nodes/{node_id}")
def patch_diagram_node(
    project_id: str,
    node_id: str,
    body: DiagramNodeUpdate,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    data = storage.get_diagram_dict(session, project_id)
    if data is None:
        raise HTTPException(404, "diagram not parsed yet")

    label = body.label.strip()
    for node in data.get("nodes") or []:
        if str(node.get("id")) == node_id:
            node["label"] = label
            props = node.get("properties")
            if not isinstance(props, dict):
                props = {}
                node["properties"] = props
            props["display_name"] = label
            break
    else:
        raise HTTPException(404, "diagram node not found")

    storage.save_diagram_json(session, project_id, data)

    try:
        from server.annotation_service import load_document, save_document

        doc = load_document(session, project_id)
        for ann in doc.annotations:
            if ann.node_id == node_id:
                ann.name = label
        save_document(session, project_id, doc)
    except Exception:
        pass

    try:
        rebuild_schema_registry(session, project_id)
    except Exception:
        pass

    return data


@router.delete("/{project_id}/diagram/nodes")
def delete_diagram_nodes(
    project_id: str,
    body: DiagramNodesDelete,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    data = storage.get_diagram_dict(session, project_id)
    if data is None:
        raise HTTPException(404, "diagram not parsed yet")

    node_ids = set(body.node_ids)
    before = len(data.get("nodes") or [])
    data["nodes"] = [n for n in data.get("nodes") or [] if str(n.get("id")) not in node_ids]
    if len(data["nodes"]) == before:
        raise HTTPException(404, "no matching diagram nodes")

    data["edges"] = [
        e
        for e in data.get("edges") or []
        if str(e.get("source")) not in node_ids and str(e.get("target")) not in node_ids
    ]
    storage.save_diagram_json(session, project_id, data)

    try:
        from server.annotation_service import load_document, save_document

        doc = load_document(session, project_id)
        doc.annotations = [a for a in doc.annotations if a.node_id not in node_ids]
        save_document(session, project_id, doc)
    except Exception:
        pass

    try:
        rebuild_schema_registry(session, project_id)
    except Exception:
        pass

    return data
