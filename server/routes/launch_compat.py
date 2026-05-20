from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from schemagraph.launch_compat import LaunchPhysicsEngine, list_launch_vehicles
from schemagraph.launch_compat.loads.parser import parse_load_file
from schemagraph.launch_compat.tests.registry import list_tests
from server.annotation_service import load_document
from server.auth import get_current_user
from server.deps import SessionDep
from server.launch_storage import load_overrides, load_report, save_overrides, save_report
from server.models import User
from server.project_access import get_accessible_project
from server.schemas import LaunchCompatRequest, LaunchCompatResponse, LaunchVehicleOut
from server import storage

router = APIRouter(tags=["launch"])


@router.get("/launch-vehicles", response_model=list[LaunchVehicleOut])
def get_launch_vehicles():
    return [LaunchVehicleOut(**v) for v in list_launch_vehicles()]


@router.get("/launch-compat/tests")
def get_physics_tests():
    return {"tests": list_tests(), "engine": "launch_physics_v2"}


@router.get("/projects/{project_id}/launch-compat/report")
def get_launch_report(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    report = load_report(session, project_id)
    if not report:
        raise HTTPException(404, "no launch report — run launch-compat first")
    return report


@router.post("/projects/{project_id}/launch-compat", response_model=LaunchCompatResponse)
def run_launch_compat(
    project_id: str,
    body: LaunchCompatRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    ann_doc = load_document(session, project_id)
    diagram = storage.get_diagram(session, project_id)
    overrides = load_overrides(session, project_id)
    try:
        result = LaunchPhysicsEngine.run_suite(
            vehicle_id=body.vehicle_id,
            orbit=body.orbit,
            profile=body.profile,
            annotations=ann_doc.annotations,
            diagram=diagram,
            load_overrides=overrides,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    save_report(session, project_id, result)
    return LaunchCompatResponse(**result)


@router.post("/projects/{project_id}/launch-compat/tests/{test_id}")
def run_single_test(
    project_id: str,
    test_id: str,
    body: LaunchCompatRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    ann_doc = load_document(session, project_id)
    diagram = storage.get_diagram(session, project_id)
    overrides = load_overrides(session, project_id)
    try:
        return LaunchPhysicsEngine.run_one(
            vehicle_id=body.vehicle_id,
            test_id=test_id,
            orbit=body.orbit,
            profile=body.profile,
            annotations=ann_doc.annotations,
            diagram=diagram,
            load_overrides=overrides,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/projects/{project_id}/launch-loads")
def get_launch_loads(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    return load_overrides(session, project_id)


@router.post("/projects/{project_id}/launch-loads")
async def upload_launch_loads(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
    kind: str = Form(...),
    file: UploadFile = File(...),
):
    get_accessible_project(session, user, project_id)
    raw = await file.read()
    try:
        parsed = parse_load_file(kind, raw, file.filename or "")
    except Exception as e:
        raise HTTPException(400, f"invalid load file: {e}") from e
    data = load_overrides(session, project_id)
    data[kind.lower()] = parsed
    save_overrides(session, project_id, data)
    return {"ok": True, "kind": kind, "keys": list(data.keys())}
