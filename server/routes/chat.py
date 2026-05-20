from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from schemagraph.instruments.sheets import SheetMissingError, SheetStore
from server.auth import get_current_user
from server.deps import SessionDep
from server.models import User
from server.project_access import get_accessible_project
from server import storage
from server.schemas import ChatRequest, ChatResponse
from server.workspace import sheet_store_root


def _gemini_client():
    from schemagraph.vlm.google_provider import GoogleProvider

    p = GoogleProvider()
    return p._client(), p.model


def _generate_reply(system: str, user: str) -> str:
    try:
        from google.genai import types  # type: ignore
    except ImportError as e:
        raise RuntimeError("Install schemagraph[google] for chat.") from e

    client, model = _gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_text(text=system),
            types.Part.from_text(text=user),
        ],
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return (response.text or "").strip() or "(empty model response)"


router = APIRouter(prefix="/projects", tags=["chat"])


@router.post("/{project_id}/chat", response_model=ChatResponse)
def chat_diagram(
    project_id: str,
    body: ChatRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    d = storage.get_diagram(session, project_id)
    if not d:
        raise HTTPException(404, "diagram not found")
    summary = {
        "node_count": len(d.nodes),
        "edge_count": len(d.edges),
        "domain": d.domain,
        "nodes": [
            {
                "id": n.id,
                "kind": n.kind,
                "label": n.label,
                "properties": n.properties,
            }
            for n in d.nodes[:80]
        ],
    }
    system = (
        "You are an engineering assistant helping interpret a parsed schematic or diagram. "
        "Answer using the structured diagram summary below. If unsure, say so.\n\n"
        f"{json.dumps(summary, indent=2, default=str)}"
    )
    try:
        reply = _generate_reply(system, body.message)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"model error: {e}") from e
    return ChatResponse(reply=reply)


@router.post("/{project_id}/chat/{node_id}", response_model=ChatResponse)
def chat_node(
    project_id: str,
    node_id: str,
    body: ChatRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    d = storage.get_diagram(session, project_id)
    if not d:
        raise HTTPException(404, "diagram not found")
    node = next((n for n in d.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(404, "node not found")
    sample_rows: list[dict] = []
    sheet_id = node.properties.get("sheet_id") if node.properties else None
    if isinstance(sheet_id, str):
        store = SheetStore(sheet_store_root(project_id))
        try:
            sample_rows = store.head(sheet_id, 8)
        except SheetMissingError:
            sample_rows = []
    system = (
        "You are a spacecraft/engineering assistant. The user asks about this diagram element.\n\n"
        f"Node properties:\n{json.dumps(dict(node.properties), indent=2, default=str)}\n\n"
        f"kind={node.kind!r} label={node.label!r}\n\n"
        f"Sample telemetry rows (if any):\n{json.dumps(sample_rows, indent=2, default=str)}"
    )
    try:
        reply = _generate_reply(system, body.message)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"model error: {e}") from e
    return ChatResponse(reply=reply)
