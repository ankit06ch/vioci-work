"""Tests for the Gemini provider's two backend modes.

We can't make real API calls in CI, so these tests poke the construction
paths and confirm:
- Vertex AI mode requires a project id,
- Developer API mode requires an API key,
- the Vertex-aware client picks up the right constructor kwargs.
"""

from __future__ import annotations

import pytest

from schemagraph.vlm.google_provider import GoogleProvider


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Isolate tests from the developer's real .env / shell.

    Without this, a real `SCHEMAGRAPH_GOOGLE_PROJECT` (or `GOOGLE_API_KEY`)
    on the contributor's machine would make our negative-path assertions
    falsely pass.
    """
    for k in (
        "GOOGLE_API_KEY",
        "SCHEMAGRAPH_GOOGLE_API_KEY",
        "SCHEMAGRAPH_GOOGLE_PROJECT",
        "SCHEMAGRAPH_GOOGLE_USE_VERTEX",
        "SCHEMAGRAPH_GOOGLE_LOCATION",
        "SCHEMAGRAPH_GOOGLE_MODEL",
    ):
        monkeypatch.delenv(k, raising=False)
    from schemagraph.config import reset_settings

    reset_settings()
    yield
    reset_settings()


def test_vertex_requires_project():
    p = GoogleProvider(use_vertex=True, project=None)
    p._project = None  # ensure no env fallback leaked through
    with pytest.raises(RuntimeError, match="SCHEMAGRAPH_GOOGLE_PROJECT"):
        p._client()


def test_developer_api_requires_key():
    p = GoogleProvider(use_vertex=False, api_key=None)
    p._api_key = None
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        p._client()


def test_vertex_client_constructor_args(monkeypatch):
    """Patch genai.Client to capture what we'd pass it on Vertex mode."""
    from google import genai  # type: ignore

    captured: dict = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(genai, "Client", FakeClient)

    p = GoogleProvider(use_vertex=True, project="my-gcp-project", location="us-central1")
    p._client()
    assert captured == {
        "vertexai": True,
        "project": "my-gcp-project",
        "location": "us-central1",
    }


def test_developer_client_constructor_args(monkeypatch):
    from google import genai  # type: ignore

    captured: dict = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(genai, "Client", FakeClient)

    p = GoogleProvider(use_vertex=False, api_key="key-abc")
    p._client()
    assert captured == {"api_key": "key-abc"}


def test_healthcheck_vertex_vs_developer():
    assert GoogleProvider(use_vertex=True, project="p").healthcheck() is True

    p_no_project = GoogleProvider(use_vertex=True, project=None)
    p_no_project._project = None
    assert p_no_project.healthcheck() is False

    assert GoogleProvider(use_vertex=False, api_key="k").healthcheck() is True

    p = GoogleProvider(use_vertex=False, api_key=None)
    p._api_key = None
    assert p.healthcheck() is False
