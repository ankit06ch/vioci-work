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


def _node_display_name(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    disp = props.get("display_name")
    if isinstance(disp, str) and disp.strip():
        return disp.strip()
    label = node.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return str(node.get("kind") or "part")


def _bbox_from_node(node: dict[str, Any]) -> BBoxPx | None:
    geom = node.get("geometry") or {}
    bb = geom.get("bbox")
    if not bb or not bb.get("w") or not bb.get("h"):
        return None
    return BBoxPx(
        x=float(bb["x"]),
        y=float(bb["y"]),
        w=float(bb["w"]),
        h=float(bb["h"]),
    )


def _auto_vectors_for_bbox(bbox: BBoxPx, name: str) -> list[AnnotationVector]:
    x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
    vid = str(uuid.uuid4())
    rect = AnnotationVector(
        id=vid,
        kind="rect",
        points=[(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        auto=True,
        label=name,
    )
    cx, cy = x + w / 2, y + h / 2
    arrow = AnnotationVector(
        id=str(uuid.uuid4()),
        kind="arrow",
        points=[(cx, max(8.0, y - 24)), (cx, y)],
        auto=True,
        label=name,
    )
    return [rect, arrow]


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
