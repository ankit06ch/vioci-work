from __future__ import annotations

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from server import events
from server.auth import decode_token
from server.config import auth_disabled
from server.project_access import get_accessible_project
from server.models import User
from server.state import get_engine

router = APIRouter(prefix="/projects", tags=["ws"])


def _user_from_token(token: str | None) -> User | None:
    if auth_disabled():
        with Session(get_engine()) as session:
            return session.exec(select(User)).first()
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    with Session(get_engine()) as session:
        return session.get(User, user_id)


@router.websocket("/{project_id}/events")
async def project_events(
    websocket: WebSocket,
    project_id: str,
    token: str | None = Query(default=None),
):
    await websocket.accept()
    user = _user_from_token(token)
    if user is None:
        await websocket.close(code=4001, reason="unauthorized")
        return
    with Session(get_engine()) as session:
        try:
            get_accessible_project(session, user, project_id)
        except Exception:
            await websocket.close(code=4004, reason="project not found")
            return
    q = events.subscribe(project_id)
    try:
        await websocket.send_json({"type": "progress", "phase": "connected", "message": "listening"})
        while True:
            event = await q.get()
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        events.unsubscribe(project_id, q)
