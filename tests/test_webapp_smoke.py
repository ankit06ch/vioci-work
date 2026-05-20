"""Smoke tests for the web API (no VLM calls)."""

from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from server import workspace
from server.main import app
from server.settings import reset_server_settings
from server.state import ProjectRecord, get_engine


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("VIOCI_AUTH_DISABLED", "1")
    monkeypatch.setenv("VIOCI_SQLITE_PATH", str(tmp_path / "idx.sqlite"))
    monkeypatch.delenv("VIOCI_DATABASE_URL", raising=False)
    monkeypatch.delenv("VIOCI_SUPABASE_URL", raising=False)
    monkeypatch.delenv("VIOCI_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path / "ws")
    reset_server_settings()
    import server.state as state

    if state._engine is not None:
        state._engine.dispose()
    state._engine = None
    import server.events as events

    events._subscribers.clear()
    with TestClient(app) as c:
        c.get("/api/health")
        c.post(
            "/api/auth/signup",
            json={
                "email": f"test-{uuid.uuid4().hex[:8]}@vioci.local",
                "password": "testpass123",
                "full_name": "Test User",
            },
        )
        yield c
    if state._engine is not None:
        state._engine.dispose()
        state._engine = None


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_auth_login(client):
    email = f"login-{uuid.uuid4().hex[:8]}@vioci.local"
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "testpass123", "full_name": "Login Test"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_image_stored_in_db(client):
    from sqlmodel import Session

    from server.models import ProjectImage
    from server.state import get_engine

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color="red").save(buf, format="PNG")
    raw = buf.getvalue()
    r = client.post("/api/projects/upload", files=[("files", ("db.png", raw, "image/png"))])
    pid = r.json()["projects"][0]["id"]
    with Session(get_engine()) as session:
        row = session.get(ProjectImage, pid)
        assert row is not None
        assert len(row.data) > 0


def test_create_folder_and_upload(client):
    r = client.post("/api/folders", json={"name": "Electrical"})
    assert r.status_code == 200
    fid = r.json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buf, format="PNG")
    raw = buf.getvalue()
    r2 = client.post(
        "/api/projects/upload",
        files=[("files", ("x.png", raw, "image/png"))],
        data={"folder_id": fid},
    )
    assert r2.status_code == 200
    assert r2.json()["projects"][0]["folder_id"] == fid


def test_api_root(client):
    r = client.get("/api")
    assert r.status_code == 200
    body = r.json()
    assert body["openapi"] == "/api/openapi.json"
    assert body["docs"] == "/api/docs"


def test_upload_list_project(client):
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color=(40, 80, 120)).save(buf, format="PNG")
    raw = buf.getvalue()
    r = client.post(
        "/api/projects/upload",
        files=[("files", ("x.png", raw, "image/png"))],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["projects"]) == 1
    pid = body["projects"][0]["id"]

    r2 = client.get("/api/projects")
    assert r2.status_code == 200
    assert any(p["id"] == pid for p in r2.json())

    with Session(get_engine()) as session:
        rec = session.get(ProjectRecord, pid)
        assert rec is not None
        assert rec.name == "x.png"


def test_delete_project(client):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(buf, format="PNG")
    raw = buf.getvalue()
    r = client.post("/api/projects/upload", files=[("files", ("a.png", raw, "image/png"))])
    pid = r.json()["projects"][0]["id"]
    r2 = client.delete(f"/api/projects/{pid}")
    assert r2.status_code == 204
    r3 = client.get(f"/api/projects/{pid}")
    assert r3.status_code == 404
