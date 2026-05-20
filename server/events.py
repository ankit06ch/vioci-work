"""In-memory pub/sub for WebSocket progress (parse / simulate)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None
_shutdown = False
# project_id -> list of asyncio.Queue dict[str, Any]
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def reset_for_startup() -> None:
    """Clear subscribers and shutdown flag (called on each app lifespan start)."""
    global _shutdown
    _shutdown = False
    _subscribers.clear()


def request_shutdown() -> None:
    """Unblock WebSocket loops so uvicorn --reload can exit promptly."""
    global _shutdown
    _shutdown = True
    sentinel = {"type": "shutdown", "phase": "shutdown", "message": "server reloading"}
    for subs in list(_subscribers.values()):
        for q in subs:
            if _loop is not None:
                _loop.call_soon_threadsafe(q.put_nowait, sentinel)
            else:
                try:
                    q.put_nowait(sentinel)
                except Exception:
                    pass


def is_shutdown() -> bool:
    return _shutdown


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe(project_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers[project_id].append(q)
    return q


def unsubscribe(project_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(project_id)
    if not subs:
        return
    if q in subs:
        subs.remove(q)
    if not subs:
        del _subscribers[project_id]


def publish(project_id: str, event: dict[str, Any]) -> None:
    """Thread-safe: safe to call from sync code running in a threadpool."""
    for q in list(_subscribers.get(project_id, [])):
        if _loop is not None:
            _loop.call_soon_threadsafe(q.put_nowait, event)
        else:
            try:
                q.put_nowait(event)
            except Exception:
                pass
