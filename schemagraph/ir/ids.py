"""Deterministic, content-hash-based ID generation for IR artifacts.

Stable IDs let us:

* diff two parses of the same diagram,
* cache expensive VLM/CV results by content hash,
* compare predicted vs golden IR in the eval harness without spurious diffs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


_NAMESPACE = "schemagraph/0.1"


def _canonical(obj: Any) -> str:
    """Stable JSON serialization (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _digest(prefix: str, payload: Any) -> str:
    h = hashlib.sha256()
    h.update(_NAMESPACE.encode())
    h.update(b"|")
    h.update(prefix.encode())
    h.update(b"|")
    h.update(_canonical(payload).encode())
    return f"{prefix}_{h.hexdigest()[:16]}"


def source_id(sha256: str | None, uri: str | None = None) -> str:
    return _digest("src", {"sha": sha256, "uri": uri})


def diagram_id(source_sha: str | None, page: int = 1) -> str:
    return _digest("dgm", {"sha": source_sha, "page": page})


def node_id(diagram: str, kind: str, anchor: tuple[float, float] | None, label: str | None) -> str:
    return _digest("n", {"d": diagram, "k": kind, "a": anchor, "l": label})


def port_id(node: str, role: str | None, position: tuple[float, float] | None) -> str:
    return _digest("p", {"n": node, "r": role, "pos": position})


def edge_id(
    diagram: str,
    source: str,
    target: str,
    polyline: Iterable[tuple[float, float]] | None = None,
) -> str:
    pts = list(polyline) if polyline is not None else None
    return _digest("e", {"d": diagram, "s": source, "t": target, "p": pts})


def constraint_id(diagram: str, kind: str, targets: Iterable[str], expression: str | None) -> str:
    return _digest("c", {"d": diagram, "k": kind, "t": sorted(targets), "x": expression})


def equation_id(diagram: str, raw: str) -> str:
    return _digest("eq", {"d": diagram, "r": raw})


def dataset_id(diagram: str, name: str | None, axes: Iterable[str]) -> str:
    return _digest("ds", {"d": diagram, "n": name, "a": list(axes)})


def parameter_id(diagram: str, name: str) -> str:
    return _digest("par", {"d": diagram, "n": name})


def primitive_id(diagram: str, kind: str, payload: Any) -> str:
    return _digest("pr", {"d": diagram, "k": kind, "x": payload})


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
