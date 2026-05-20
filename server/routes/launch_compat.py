from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from schemagraph.launch_compat import compute_launch_compatibility, list_launch_vehicles
from server.annotation_service import load_document
from server.auth import get_current_user
from server.deps import SessionDep
from server.models import User
from server.project_access import get_accessible_project
from server.schemas import LaunchCompatRequest, LaunchCompatResponse, LaunchVehicleOut

router = APIRouter(tags=["launch"])


@router.get("/launch-vehicles", response_model=list[LaunchVehicleOut])
def get_launch_vehicles():
    return [LaunchVehicleOut(**v) for v in list_launch_vehicles()]


@router.post("/projects/{project_id}/launch-compat", response_model=LaunchCompatResponse)
def run_launch_compat(
    project_id: str,
    body: LaunchCompatRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    ann_doc = load_document(session, project_id)
    try:
        result = compute_launch_compatibility(
            vehicle_id=body.vehicle_id,
            orbit=body.orbit,
            profile=body.profile,
            annotations=ann_doc.annotations,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return LaunchCompatResponse(**result)
