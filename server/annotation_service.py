"""Persist and seed schematic part annotations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from server.annotation_schemas import (
    AnnotationsDocument,
    AnnotationVector,
    BBoxPx,
    PartAnnotation,
)
from server.models import ProjectAnnotations


def _humanize_name(raw: str) -> str:
    t = raw.strip().replace("_", " ").replace("-", " ")
    if not t:
        return "Component"
    if t.isupper() and len(t) <= 6:
        return t
    return t[:1].upper() + t[1:]


def _node_display_name(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    disp = props.get("display_name")
    if isinstance(disp, str) and disp.strip():
        return _humanize_name(disp)
    label = node.get("label")
    if isinstance(label, str) and label.strip():
        return _humanize_name(label)
    kind = node.get("kind")
    if isinstance(kind, str) and kind.strip():
        return _humanize_name(kind)
    return "Component"


def _bbox_from_node(node: dict[str, Any]) -> BBoxPx | None:
    geom = node.get("geometry") or {}
    bb = geom.get("bbox")
    if bb and bb.get("w") and bb.get("h"):
        return BBoxPx(
            x=float(bb["x"]),
            y=float(bb["y"]),
            w=float(bb["w"]),
            h=float(bb["h"]),
        )
    pl = geom.get("polyline_px")
    if pl and len(pl) >= 2:
        xs = [float(p[0]) for p in pl]
        ys = [float(p[1]) for p in pl]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return BBoxPx(
            x=min_x,
            y=min_y,
            w=max(16.0, max_x - min_x),
            h=max(16.0, max_y - min_y),
        )
    ports = node.get("ports") or []
    px = [float(p["position_px"][0]) for p in ports if p.get("position_px")]
    py = [float(p["position_px"][1]) for p in ports if p.get("position_px")]
    if px and py:
        pad = 36.0
        min_x, max_x = min(px), max(px)
        min_y, max_y = min(py), max(py)
        return BBoxPx(
            x=min_x - pad,
            y=min_y - pad,
            w=max(24.0, max_x - min_x + 2 * pad),
            h=max(24.0, max_y - min_y + 2 * pad),
        )
    return None


def _auto_vectors_for_bbox(bbox: BBoxPx, name: str) -> list[AnnotationVector]:
    """Outline the component (not the caption text box)."""
    x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
    return [
        AnnotationVector(
            id=str(uuid.uuid4()),
            kind="rect",
            points=[(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
            auto=True,
            label=name,
        ),
    ]


def seed_from_diagram(
    diagram: dict[str, Any],
    existing: list[PartAnnotation] | None = None,
) -> list[PartAnnotation]:
    """Merge diagram nodes into annotations; preserve user edits by node_id."""
    by_node: dict[str, PartAnnotation] = {}
    if existing:
        for a in existing:
            if a.node_id:
                by_node[a.node_id] = a

    out: list[PartAnnotation] = []
    seen_nodes: set[str] = set()
    for node in diagram.get("nodes") or []:
        nid = str(node.get("id") or "")
        if not nid:
            continue
        seen_nodes.add(nid)
        name = _node_display_name(node)
        bbox = _bbox_from_node(node)
        if nid in by_node:
            prev = by_node[nid]
            if bbox and not prev.bbox:
                prev.bbox = bbox
            if not prev.vectors and bbox:
                prev.vectors = _auto_vectors_for_bbox(bbox, prev.name or name)
            if prev.name != name and prev.auto_detected:
                prev.name = name
            out.append(prev)
            continue
        vectors: list[AnnotationVector] = []
        if bbox:
            vectors = _auto_vectors_for_bbox(bbox, name)
        out.append(
            PartAnnotation(
                id=str(uuid.uuid4()),
                node_id=nid,
                name=name,
                auto_detected=True,
                bbox=bbox,
                vectors=vectors,
            )
        )

    for a in existing or []:
        if a.node_id and a.node_id not in seen_nodes:
            continue
        if not a.node_id:
            out.append(a)
    return out


def load_document(session: Session, project_id: str) -> AnnotationsDocument:
    row = session.get(ProjectAnnotations, project_id)
    if not row:
        return AnnotationsDocument()
    data = json.loads(row.json_text)
    return AnnotationsDocument.model_validate(data)


def save_document(
    session: Session,
    project_id: str,
    doc: AnnotationsDocument,
) -> None:
    text = doc.model_dump(mode="json")
    now = datetime.now(timezone.utc)
    row = session.get(ProjectAnnotations, project_id)
    payload = json.dumps(text, indent=2)
    if row:
        row.json_text = payload
        row.updated_at = now
        session.add(row)
    else:
        session.add(
            ProjectAnnotations(
                project_id=project_id,
                json_text=payload,
                updated_at=now,
            )
        )
    session.commit()


def sync_from_diagram(session: Session, project_id: str, diagram: dict[str, Any]) -> AnnotationsDocument:
    """AI auto-detect: diagram nodes + OCR labels → overlays (preserves manual edits by node_id)."""
    from server import storage
    from server.annotation_detect import auto_detect_annotations

    doc = load_document(session, project_id)
    blob = storage.get_image(session, project_id)
    if blob:
        merged = auto_detect_annotations(blob[0], diagram, doc.annotations)
    else:
        merged = seed_from_diagram(diagram, doc.annotations)
    doc.annotations = merged
    save_document(session, project_id, doc)
    return doc
