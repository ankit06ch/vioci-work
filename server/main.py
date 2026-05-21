from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("vioci.api")

from server import events
from server.routes import (
    annotations,
    auth,
    chat,
    folders,
    launch_compat,
    parse,
    projects,
    schema_registry,
    sheets,
    simulate,
    ws,
)
from schemagraph.config import get_settings as get_schemagraph_settings

from server.cloud_files import cloud_storage_enabled
from server.gcp_auth import configure_vertex_adc
from server.settings import get_server_settings
from server.state import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    events.reset_for_startup()
    events.set_loop(asyncio.get_running_loop())
    init_db()
    sg = get_schemagraph_settings()
    if sg.google_use_vertex:
        adc_path = configure_vertex_adc()
        if adc_path:
            print(f"[vioci] vertex ADC: {adc_path}", flush=True)
        else:
            print("[vioci] vertex ADC: application-default (gcloud or metadata)", flush=True)
    s = get_server_settings()
    if s.database_url:
        mode = "cloud postgres"
        if cloud_storage_enabled():
            mode += f" + storage bucket '{s.supabase_bucket}'"
    else:
        mode = "local sqlite"
    print(f"[vioci] database: {mode}", flush=True)
    print("[vioci] API ready — http://127.0.0.1:8000/api/health", flush=True)
    yield
    events.request_shutdown()


API_DESCRIPTION = """
HTTP API for **Vioci Schemagraph** — ingest diagrams, extract IR, attach telemetry CSVs,
run Gemini chat, and execute simulations.

## Features

| Area | Prefix | Description |
|------|--------|-------------|
| Projects | `/api/projects` | Upload images, list/delete, fetch source image & diagram IR |
| Parse | `POST …/parse` | Queue async parse (Google Gemini + autodetect) |
| Events | `WS …/events` | Real-time parse/sim progress |
| Sheets | `/api/projects/…/sheets` | CSV telemetry per node |
| Chat | `POST …/chat` | Diagram- or node-level Gemini Q&A |
| Simulate | `POST …/simulate`, `…/sweep` | Parameter runs & sweeps |

Human-readable guide: run the web app and open **API Documentation** (`/docs`), or see `webapp/src/api/reference.ts`.

**Local dev:** `make dev` — API on port 8000, UI on 5173 (proxies `/api`).
"""

app = FastAPI(
    title="Vioci Schemagraph API",
    description=API_DESCRIPTION,
    version="0.9.1",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

_cors_origins = [
    o.strip()
    for o in (get_server_settings().cors_origins or "").split(",")
    if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    path = request.url.path
    if path.startswith("/api"):
        print(f"[api] {request.method} {path}", flush=True)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("%s %s failed", request.method, path)
        raise
    if path.startswith("/api"):
        ms = (time.perf_counter() - t0) * 1000
        print(f"[api] {request.method} {path} -> {response.status_code} ({ms:.0f}ms)", flush=True)
    return response


@app.get("/api")
def api_root():
    return {
        "name": "Vioci Schemagraph API",
        "version": app.version,
        "health": "/api/health",
        "openapi": "/api/openapi.json",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "human_docs": "Open the web UI route /docs for examples and curl recipes.",
    }


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(schema_registry.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
app.include_router(sheets.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(launch_compat.router, prefix="/api")
app.include_router(ws.router, prefix="/api")
