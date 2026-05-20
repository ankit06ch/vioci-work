from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from schemagraph.ir.schema import Dataset
from server import events, storage
from server.auth import get_current_user
from server.deps import SessionDep
from server.models import User
from server.project_access import get_accessible_project
from server.schemas import SimulateRequest, SweepRequest

router = APIRouter(prefix="/projects", tags=["simulate"])


def _serialize_dataset(ds: Dataset) -> dict[str, Any]:
    return {
        "id": ds.id,
        "name": ds.name,
        "axes": ds.axes,
        "series": [{"name": s.name, "values": s.values} for s in ds.series],
    }


def _serialize_result(engine: str, result) -> dict[str, Any]:
    return {
        "engine": result.engine,
        "success": result.success,
        "log": result.log,
        "artifacts": result.artifacts,
        "metadata": result.metadata,
        "datasets": [_serialize_dataset(d) for d in result.datasets],
    }


@router.post("/{project_id}/simulate")
def simulate_project(
    project_id: str,
    body: SimulateRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    d = storage.get_diagram(session, project_id)
    if not d:
        raise HTTPException(404, "diagram not found")
    events.publish(
        project_id,
        {"type": "progress", "phase": "simulate", "progress": 0.5, "message": "running simulation"},
    )
    try:
        from schemagraph import simulate as run_sim

        result = run_sim(d, engine=body.engine, parameters=body.overrides or None)
    except Exception as e:
        events.publish(
            project_id,
            {"type": "error", "phase": "simulate", "message": str(e)},
        )
        raise HTTPException(400, str(e)) from e
    events.publish(
        project_id,
        {"type": "progress", "phase": "simulate_done", "progress": 1.0, "message": "simulation complete"},
    )
    return _serialize_result(body.engine, result)


@router.post("/{project_id}/sweep")
def sweep_project(
    project_id: str,
    body: SweepRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    d = storage.get_diagram(session, project_id)
    if not d:
        raise HTTPException(404, "diagram not found")
    from schemagraph import simulate as run_sim
    from schemagraph.physics.parametric import sweep

    out: list[dict[str, Any]] = []
    for overrides, diagram in sweep(d, body.axis):
        try:
            result = run_sim(diagram, engine=body.engine, parameters=None)
        except Exception as e:
            out.append({"overrides": overrides, "error": str(e)})
            continue
        summary = _serialize_result(body.engine, result)
        out.append({"overrides": overrides, "result": summary})
    return out
