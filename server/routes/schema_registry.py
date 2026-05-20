from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from server.auth import get_current_user
from server.deps import SessionDep
from server.models import User
from server.project_access import get_accessible_project
from server.schema_registry import (
    REGISTRY_TABLES,
    list_registry_files,
    load_schema_registry,
    query_registry,
    rebuild_schema_registry,
    registry_csv_bytes,
)
from server.schema_registry_sql import (
    append_row,
    delete_row,
    run_sql,
    update_row,
)
from server.schemas import (
    SchemaRegistryMetaSummary,
    SchemaRegistryOut,
    SchemaRegistryQueryOut,
    SchemaRegistryRowCreate,
    SchemaRegistryRowUpdate,
    SchemaRegistrySqlRequest,
    SchemaRegistrySqlResponse,
)

router = APIRouter(prefix="/projects", tags=["schema-registry"])


@router.get("/{project_id}/schema-registry/files")
def get_schema_registry_files(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    files = list_registry_files(project_id)
    if not files:
        raise HTTPException(404, "schema registry not created yet")
    return {"files": files}


@router.get("/{project_id}/schema-registry", response_model=SchemaRegistryOut)
def get_schema_registry(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    doc = load_schema_registry(project_id)
    if doc is None:
        raise HTTPException(404, "schema registry not created yet")
    return doc


@router.get("/{project_id}/schema-registry/query", response_model=SchemaRegistryQueryOut)
def query_schema_registry(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
    table: str = Query(default="components", pattern="^(components|dependencies|properties)$"),
    q: str | None = None,
    full: bool = Query(default=False, description="Return all matching rows (no 5k cap)"),
):
    get_accessible_project(session, user, project_id)
    doc = load_schema_registry(project_id)
    if doc is None:
        raise HTTPException(404, "schema registry not created yet")
    result = query_registry(doc, table, q=q, limit=None if full else 5000)
    meta = SchemaRegistryMetaSummary(
        updated_at=str(doc.get("updated_at") or ""),
        parse_status=str(doc.get("parse_status") or ""),
        last_domain=doc.get("last_domain"),
        node_count=int(doc.get("node_count") or 0),
        edge_count=int(doc.get("edge_count") or 0),
        part_count=int(doc.get("part_count") or 0),
        project_name=str(doc.get("project_name") or ""),
    )
    return SchemaRegistryQueryOut(table=table, meta=meta, **result)


@router.post("/{project_id}/schema-registry/refresh", response_model=SchemaRegistryOut)
def refresh_schema_registry(
    project_id: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    try:
        return rebuild_schema_registry(session, project_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{project_id}/schema-registry/csv/{table}")
def download_schema_csv(
    project_id: str,
    table: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    if table not in ("components", "dependencies", "properties"):
        raise HTTPException(400, "table must be components, dependencies, or properties")
    data = registry_csv_bytes(project_id, table)
    if data is None:
        raise HTTPException(404, "schema CSV not found")
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
    )


@router.get("/{project_id}/schema-registry/csv/{table}/preview", response_class=PlainTextResponse)
def preview_schema_csv(
    project_id: str,
    table: str,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    if table not in ("components", "dependencies", "properties"):
        raise HTTPException(400, "invalid table")
    data = registry_csv_bytes(project_id, table)
    if data is None:
        raise HTTPException(404, "schema CSV not found")
    return PlainTextResponse(data.decode("utf-8"))


@router.patch("/{project_id}/schema-registry/tables/{table}/rows/{row_index}")
def patch_registry_row(
    project_id: str,
    table: str,
    row_index: int,
    body: SchemaRegistryRowUpdate,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    if table not in REGISTRY_TABLES:
        raise HTTPException(400, "invalid table")
    try:
        return update_row(project_id, table, row_index, body.values)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except IndexError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/{project_id}/schema-registry/tables/{table}/rows/{row_index}")
def remove_registry_row(
    project_id: str,
    table: str,
    row_index: int,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    if table not in REGISTRY_TABLES:
        raise HTTPException(400, "invalid table")
    try:
        return delete_row(project_id, table, row_index)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except IndexError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/{project_id}/schema-registry/tables/{table}/rows")
def create_registry_row(
    project_id: str,
    table: str,
    body: SchemaRegistryRowCreate,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    if table not in REGISTRY_TABLES:
        raise HTTPException(400, "invalid table")
    try:
        return append_row(project_id, table, body.values)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{project_id}/schema-registry/sql", response_model=SchemaRegistrySqlResponse)
def execute_registry_sql(
    project_id: str,
    body: SchemaRegistrySqlRequest,
    session: SessionDep,
    user: User = Depends(get_current_user),
):
    get_accessible_project(session, user, project_id)
    try:
        result = run_sql(project_id, body.sql)
        return SchemaRegistrySqlResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
