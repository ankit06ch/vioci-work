"""Vertex AI credentials for server hosts without gcloud (e.g. Render)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def configure_vertex_adc() -> str | None:
    """Write service-account JSON to disk and set GOOGLE_APPLICATION_CREDENTIALS.

    Local dev: use ``gcloud auth application-default login`` (no JSON env needed).
    Production: set ``GOOGLE_APPLICATION_CREDENTIALS_JSON`` to the full key file contents.
    """
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    if not raw:
        return None

    try:
        json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS_JSON is set but is not valid JSON."
        ) from e

    path = Path(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_PATH", "/tmp/gcp-adc.json"))
    path.write_text(raw, encoding="utf-8")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    return str(path)
