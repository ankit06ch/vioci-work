from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server import storage
from server.annotation_schemas import AnnotationsDocument, AnnotationsUpdate, EnhanceImageResult
from server.annotation_service import load_document, save_document, sync_from_diagram
from server.auth import get_current_user
from server.deps import SessionDep
from server.annotation_detect import auto_detect_annotations
from server.image_enhance import assess_quality, enhance_image_gentle
from server.models import ProjectRecord, User
from server.project_access import get_accessible_project
from server.schemas import ProjectOut

router = APIRouter(prefix="/projects", tags=["annotations"])


def _to_out(session, rec: ProjectRecord) -> ProjectOut:
    from server.routes.projects import _to_out as project_out

    return project_out(session, rec)


@router.get("/{project_id}/annotations", response_model=AnnotationsDocument)
def get_annotations(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    return load_document(session, project_id)


@router.put("/{project_id}/annotations", response_model=AnnotationsDocument)
def put_annotations(
    project_id: str,
    body: AnnotationsUpdate,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    doc = load_document(session, project_id)
    doc.annotations = body.annotations
    save_document(session, project_id, doc)
    return doc


@router.post("/{project_id}/annotations/sync", response_model=AnnotationsDocument)
def sync_annotations(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Re-run AI overlay detection from diagram IR + OCR."""
    get_accessible_project(session, user, project_id)
    data = storage.get_diagram_dict(session, project_id)
    diagram = data if data is not None else {"nodes": []}
    return sync_from_diagram(session, project_id, diagram)


@router.post("/{project_id}/annotations/auto-detect", response_model=AnnotationsDocument)
def auto_detect(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    blob = storage.get_image(session, project_id)
    if not blob:
        raise HTTPException(404, "image missing")
    data = storage.get_diagram_dict(session, project_id)
    doc = load_document(session, project_id)
    doc.annotations = auto_detect_annotations(blob[0], data, doc.annotations)
    save_document(session, project_id, doc)
    return doc


@router.post("/{project_id}/image/enhance", response_model=EnhanceImageResult)
def enhance_project_image(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    rec = get_accessible_project(session, user, project_id)
    blob = storage.get_image(session, project_id)
    if not blob:
        raise HTTPException(404, "image missing")
    data, mime = blob
    storage.backup_original_image(project_id, data)
    score = assess_quality(data)
    enhanced_bytes = enhance_image_gentle(data)
    msg = "Schematic sharpened (color preserved)"
    storage.save_image(session, project_id, enhanced_bytes, mime)
    rec.image_enhanced = True
    rec.image_quality_score = assess_quality(enhanced_bytes)
    session.add(rec)
    session.commit()
    doc = load_document(session, project_id)
    doc.image_enhanced = rec.image_enhanced
    doc.image_quality_score = rec.image_quality_score
    save_document(session, project_id, doc)
    return EnhanceImageResult(
        enhanced=True,
        quality_score=rec.image_quality_score or score,
        message=msg,
    )


@router.post("/{project_id}/image/restore", response_model=EnhanceImageResult)
def restore_project_image(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    """Restore upload from backup (fixes washed-out enhance)."""
    rec = get_accessible_project(session, user, project_id)
    if not storage.restore_original_image(session, project_id):
        raise HTTPException(404, "no original schematic backup found")
    rec.image_enhanced = False
    rec.image_quality_score = assess_quality(storage.get_image(session, project_id)[0])
    session.add(rec)
    session.commit()
    doc = load_document(session, project_id)
    doc.image_enhanced = False
    doc.image_quality_score = rec.image_quality_score
    save_document(session, project_id, doc)
    return EnhanceImageResult(
        enhanced=False,
        quality_score=rec.image_quality_score or 0.0,
        message="Restored original schematic",
    )
