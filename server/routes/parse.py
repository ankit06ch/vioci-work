from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from server import events, storage, workspace
from server.auth import get_current_user
from server.deps import SessionDep
from server.models import ProjectRecord, User
from server.project_access import get_accessible_project
from server.schemas import ParseQueued, ParseRequest
from server.state import get_engine

router = APIRouter(prefix="/projects", tags=["parse"])


def enqueue_parse(project_id: str, body: ParseRequest | None = None) -> None:
    """Queue background IR parse for a project that already has a source image."""
    req = body or ParseRequest()
    with Session(get_engine()) as session:
        rec = session.get(ProjectRecord, project_id)
        if rec:
            rec.parse_status = "queued"
            rec.parse_error = None
            session.add(rec)
            session.commit()
    threading.Thread(
        target=_run_parse,
        args=(project_id, req),
        daemon=True,
        name=f"parse-{project_id[:8]}",
    ).start()


def _run_parse(project_id: str, _body: ParseRequest) -> None:
    from schemagraph.autodetect import infer_annotation_domain, infer_handdrawn

    def _fail(msg: str) -> None:
        with Session(get_engine()) as session:
            rec = session.get(ProjectRecord, project_id)
            if rec:
                rec.parse_status = "error"
                rec.parse_error = msg
                session.add(rec)
                session.commit()
        events.publish(
            project_id,
            {"type": "error", "phase": "error", "message": msg, "progress": 0.0},
        )

    try:
        with Session(get_engine()) as session:
            img_path = str(storage.ensure_source_image_file(session, project_id))
    except FileNotFoundError as e:
        _fail(str(e))
        return

    try:
        hand = infer_handdrawn(img_path)
    except Exception as e:
        _fail(f"hand-drawn detection failed: {e}")
        return

    with Session(get_engine()) as session:
        rec = session.get(ProjectRecord, project_id)
        if not rec:
            return
        rec.parse_status = "running"
        rec.parse_error = None
        rec.last_provider = "google"
        rec.last_domain = None
        rec.handdrawn = hand
        session.add(rec)
        session.commit()

    events.publish(
        project_id,
        {
            "type": "progress",
            "phase": "parse",
            "progress": 0.08,
            "message": f"auto: hand-drawn pipeline={'on' if hand else 'off'} (Gemini)",
        },
    )
    ann_domain = "generic"
    try:
        import schemagraph

        diagram = schemagraph.parse(
            img_path,
            provider="google",
            domain=None,
            handdrawn=hand,
        )
        ann_domain = infer_annotation_domain(diagram)
        events.publish(
            project_id,
            {
                "type": "progress",
                "phase": "annotate",
                "progress": 0.65,
                "message": f'annotating as "{ann_domain}"',
            },
        )
        diagram = schemagraph.annotate(diagram, domain=ann_domain)
        payload = diagram.model_dump(mode="json")
        with Session(get_engine()) as session:
            storage.save_diagram_json(session, project_id, payload)
            from server.annotation_service import sync_from_diagram

            sync_from_diagram(session, project_id, payload)
            from server.schema_registry import rebuild_schema_registry

            rebuild_schema_registry(session, project_id)
    except Exception as e:
        _fail(str(e))
        return

    with Session(get_engine()) as session:
        rec = session.get(ProjectRecord, project_id)
        if rec:
            rec.parse_status = "done"
            rec.parse_error = None
            rec.last_provider = "google"
            rec.last_domain = ann_domain
            rec.handdrawn = hand
            session.add(rec)
            session.commit()
    events.publish(
        project_id,
        {"type": "progress", "phase": "done", "progress": 1.0, "message": "complete"},
    )


@router.post("/{project_id}/parse", response_model=ParseQueued)
def queue_parse(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
    body: ParseRequest | None = None,
):
    get_accessible_project(session, user, project_id)
    if storage.get_image(session, project_id) is None:
        raise HTTPException(400, "project has no source image")

    enqueue_parse(project_id, body)
    return ParseQueued()
