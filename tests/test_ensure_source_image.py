from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from server.models import ProjectImage, ProjectRecord
import server.state as state
from server.settings import reset_server_settings
from server.storage import ensure_source_image_file


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("VIOCI_SQLITE_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("VIOCI_DATABASE_URL", "")
    monkeypatch.delenv("VIOCI_SUPABASE_URL", raising=False)
    monkeypatch.delenv("VIOCI_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    reset_server_settings()
    if state._engine is not None:
        state._engine.dispose()
    state._engine = None
    state.init_db()
    with Session(state.get_engine()) as session:
        yield session


def test_ensure_source_image_hydrates_from_postgres(
    db_session, tmp_path, monkeypatch, small_rc_circuit_png
):
    pid = "proj-hydrate"
    cache = tmp_path / "cache"
    monkeypatch.setattr("server.workspace._use_cloud_files", lambda: False)
    monkeypatch.setattr("server.workspace._local_workspace_root", lambda: cache)

    db_session.add(
        ProjectRecord(
            id=pid,
            name="t.png",
            owner_id="user-test",
            organization_id=None,
            created_at=datetime.now(timezone.utc),
            parse_status="idle",
        )
    )
    db_session.add(
        ProjectImage(project_id=pid, data=small_rc_circuit_png, mime_type="image/png")
    )
    db_session.commit()

    path = ensure_source_image_file(db_session, pid)
    assert path == cache / pid / "source.png"
    assert path.read_bytes() == small_rc_circuit_png
