"""Heuristics for hand-drawn raster detection and annotation-domain selection.

Used by the web server and any caller that wants a zero-config parse: always
combined with ``provider="google"``, ``domain=None`` for the VLM, then
:class:`infer_annotation_domain` after fusion picks the physics annotator.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Ensure spacecraft (and other instrument) annotators are registered.
import schemagraph.instruments  # noqa: F401
from schemagraph.instruments.catalog import default_catalog
from schemagraph.ir.schema import Diagram
from schemagraph.physics.annotators import annotator_registry

# --- Hand-drawn (CV heuristic; tunable) ---------------------------------
# Crisp vector-style exports and CAD screenshots tend to have *higher* Laplacian
# variance (sharp ink edges) than pencil / pen sketches on the fixtures we ship.
# Ambiguous band defaults to digital (handdrawn=False).

_DIGITAL_LAP_MIN = 430.0
_SKETCH_LAP_MAX = 385.0
_SKETCH_EDGE_MAX = 0.07

# --- Domain scoring ------------------------------------------------------

_ELECTRICAL_KINDS = frozenset(
    {
        "resistor",
        "capacitor",
        "inductor",
        "voltage-source",
        "current-source",
        "ground",
        "wire",
        "node",
        "junction",
        "op-amp",
        "mosfet",
        "diode",
        "transformer",
        "switch",
        "source",
    }
)
_MECHANICAL_KINDS = frozenset(
    {
        "beam",
        "truss",
        "bar",
        "fixed_support",
        "fixed",
        "anchor",
        "roller",
        "roller_support",
        "joint",
        "link",
        "spring",
        "damper",
        "mass",
    }
)
_FLUID_KINDS = frozenset({"pipe", "valve", "pump", "reservoir", "inlet", "outlet"})
_THERMAL_KINDS = frozenset(
    {"heat_source", "thermal_resistance", "thermal_capacitance", "temperature"}
)
_CONTROL_KINDS = frozenset(
    {
        "gain",
        "integrator",
        "lowpass",
        "delay",
        "filter",
        "block",
        "summation",
        "sum",
        "controller",
        "plant",
    }
)
_GRAPH_HINT_KINDS = frozenset(
    {"plot", "chart", "axis", "curve", "dataset", "graph", "figure"}
)

_DOMAIN_NORMALIZE = {
    "electric": "electrical",
    "ee": "electrical",
    "circuit": "electrical",
    "mech": "mechanical",
    "structure": "mechanical",
    "thermal": "thermal",
    "heat": "thermal",
    "fluid": "fluid",
    "hydraulic": "fluid",
    "control": "control",
    "block_diagram": "control",
    "spacecraft": "spacecraft",
    "satellite": "spacecraft",
    "instrument": "spacecraft",
    "graph": "graph",
    "plot": "graph",
}


def infer_handdrawn(image_path: str | Path) -> bool:
    """True if the raster likely benefits from hand-drawn CV + prompt path.

    Crisp CAD / vector-style PNGs usually have *higher* Laplacian variance than
    softer pencil sketches on our fixtures; ambiguous images default to the
    digital (non-handdrawn) pipeline.
    """
    try:
        import cv2  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("infer_handdrawn requires opencv-python") from e

    path = Path(image_path)
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return False

    h, w = gray.shape[:2]
    m = max(h, w)
    if m > 640:
        scale = 640.0 / m
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    lap = cv2.Laplacian(blur, cv2.CV_64F)
    lap_var = float(lap.var())

    edges = cv2.Canny(blur, 45, 135)
    edge_ratio = float(np.mean(edges > 0))

    if lap_var >= _DIGITAL_LAP_MIN:
        return False
    if lap_var <= _SKETCH_LAP_MAX and edge_ratio <= _SKETCH_EDGE_MAX:
        return True
    return False


def infer_annotation_domain(diagram: Diagram) -> str:
    """Pick a single built-in annotator name from fused node content + VLM domain."""
    catalog = default_catalog()
    scores: dict[str, float] = {n: 0.0 for n in annotator_registry.names()}

    raw_dom = (diagram.domain or "").strip().lower()
    if raw_dom:
        dom = _DOMAIN_NORMALIZE.get(raw_dom, raw_dom)
        if dom in scores and dom != "generic":
            scores[dom] += 4.0
        elif dom in scores:
            scores[dom] += 1.5

    for n in diagram.nodes:
        k = (n.kind or "").lower()
        lab = (n.label or "").lower()

        if catalog.match(n.label or "") or catalog.match(n.kind or ""):
            scores["spacecraft"] = scores.get("spacecraft", 0.0) + 3.0

        if k in _ELECTRICAL_KINDS or any(
            t in lab for t in ("ohm", "µf", "uf ", "nf ", "pf ", "vdc", "vac", "kω")
        ):
            scores["electrical"] = scores.get("electrical", 0.0) + 1.2
        if k in _MECHANICAL_KINDS:
            scores["mechanical"] = scores.get("mechanical", 0.0) + 1.2
        if k in _FLUID_KINDS:
            scores["fluid"] = scores.get("fluid", 0.0) + 1.2
        if k in _THERMAL_KINDS:
            scores["thermal"] = scores.get("thermal", 0.0) + 1.2
        if k in _CONTROL_KINDS or "transfer" in lab or "h(s)" in lab or "g(s)" in lab:
            scores["control"] = scores.get("control", 0.0) + 1.2
        if k in _GRAPH_HINT_KINDS or "vs." in lab or "time (s)" in lab:
            scores["graph"] = scores.get("graph", 0.0) + 1.0

    best_score = max(scores.values())
    if best_score < 0.75:
        return "generic"

    at_best = [d for d in scores if abs(scores[d] - best_score) < 1e-9]
    priority = (
        "spacecraft",
        "electrical",
        "control",
        "mechanical",
        "fluid",
        "thermal",
        "graph",
        "generic",
    )
    for d in priority:
        if d in at_best:
            return d
    return at_best[0]
