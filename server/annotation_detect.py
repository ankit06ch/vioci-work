"""AI-assisted part detection: diagram IR + CV shapes; OCR names components only."""

from __future__ import annotations

import io
import re
import uuid
from collections import defaultdict
from typing import Any

import numpy as np

from server.annotation_schemas import AnnotationVector, BBoxPx, PartAnnotation
from server.annotation_service import (
    _auto_vectors_for_bbox,
    _bbox_from_node,
    _humanize_name,
    _node_display_name,
    is_axis_reference_label,
    seed_from_diagram,
)

# Text-like OCR / junk — never become standalone parts
_BAD_NAMES = frozenset({"label", "part", "text", "img", "image", "ref", "note", "title"})
_JUNK_LABEL_PHRASES = frozenset(
    {
        "orbit direction",
        "sensory ring",
        "attitude control subsystem",
    }
)


def _expand_bbox(bb: BBoxPx, pad: float, max_w: float, max_h: float) -> BBoxPx:
    x = max(0.0, bb.x - pad)
    y = max(0.0, bb.y - pad)
    w = min(max_w - x, bb.w + 2 * pad)
    h = min(max_h - y, bb.h + 2 * pad)
    return BBoxPx(x=x, y=y, w=max(16.0, w), h=max(16.0, h))


def _iou(a: BBoxPx, b: BBoxPx) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def _center(bb: BBoxPx) -> tuple[float, float]:
    return (bb.x + bb.w / 2, bb.y + bb.h / 2)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _is_text_like_box(bb: BBoxPx) -> bool:
    """Thin or tiny boxes are usually captions, not components."""
    if bb.w < 12 or bb.h < 10:
        return True
    aspect = bb.w / max(bb.h, 1)
    if aspect > 8 or aspect < 0.12:
        return True
    if bb.w * bb.h < 400:
        return True
    return False


def _clean_ocr_name(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) < 2:
        return None
    if is_axis_reference_label(t):
        return None
    low = t.lower()
    if low in _BAD_NAMES:
        return None
    if low.startswith("region-"):
        return None
    if re.fullmatch(r"[\W\d_]+", t):
        return None
    return _humanize_name(t)


def _ocr_labels_only(png_bytes: bytes) -> list[tuple[str, BBoxPx, float]]:
    """OCR text spans for naming — never used as component geometry."""
    import io

    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    spans: list[tuple[str, BBoxPx, float]] = []
    try:
        from schemagraph.cv.ocr import detect_text_spans

        for t in detect_text_spans(gray):
            name = _clean_ocr_name(t.text or "")
            if not name:
                continue
            if t.confidence < 0.3:
                continue
            bb = t.bbox
            box = BBoxPx(x=float(bb.x), y=float(bb.y), w=float(bb.w), h=float(bb.h))
            spans.append((name, box, float(t.confidence)))
    except Exception:
        pass
    return spans


def _is_component_label(name: str) -> bool:
    t = re.sub(r"\s+", " ", name.strip())
    if len(t) < 4:
        return False
    if is_axis_reference_label(t):
        return False
    low = t.lower()
    if low in _BAD_NAMES or low in _JUNK_LABEL_PHRASES:
        return False
    return True


def _is_huge_bbox(bb: BBoxPx, img_w: float, img_h: float, max_frac: float = 0.28) -> bool:
    area = bb.w * bb.h
    return area > max_frac * img_w * img_h


def _name_match_score(node_name: str, ocr_name: str) -> float:
    a = set(re.findall(r"[a-z0-9]+", node_name.lower()))
    b = set(re.findall(r"[a-z0-9]+", ocr_name.lower()))
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


def _find_ocr_box_for_name(name: str, ocr: list[tuple[str, BBoxPx, float]]) -> BBoxPx | None:
    best: tuple[float, BBoxPx] | None = None
    for ocr_name, box, conf in ocr:
        score = _name_match_score(name, ocr_name)
        if score < 0.45:
            continue
        rank = (1.0 - score) * 100 - conf * 10
        if best is None or rank < best[0]:
            best = (rank, box)
    return best[1] if best else None


def _polyline_points(edge: dict[str, Any]) -> list[tuple[float, float]]:
    raw = edge.get("polyline_px") or []
    pts: list[tuple[float, float]] = []
    for p in raw:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append((float(p[0]), float(p[1])))
    return pts


def _diagram_primitives_lines(diagram: dict[str, Any]) -> list[list[tuple[float, float]]]:
    prim = diagram.get("primitives") or {}
    lines: list[list[tuple[float, float]]] = []
    for sh in prim.get("shapes") or []:
        if sh.get("kind") != "line":
            continue
        pts = _polyline_points({"polyline_px": sh.get("points") or []})
        if len(pts) >= 2:
            lines.append(pts)
    return lines


def _dist_to_box(pt: tuple[float, float], box: BBoxPx) -> float:
    cx = min(max(pt[0], box.x), box.x + box.w)
    cy = min(max(pt[1], box.y), box.y + box.h)
    return _dist(pt, (cx, cy))


def _sample_polyline(pl: list[tuple[float, float]], step: float = 8.0) -> list[tuple[float, float]]:
    if len(pl) < 2:
        return pl
    out = [pl[0]]
    for i in range(1, len(pl)):
        a, b = pl[i - 1], pl[i]
        seg = _dist(a, b)
        if seg < 1e-6:
            continue
        n = max(1, int(seg / step))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _polyline_match_score(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 1e6
    sa, sb = _sample_polyline(a), _sample_polyline(b)
    return min(_dist(p, min(sb, key=lambda q: _dist(p, q))) for p in sa)


def _merge_with_primitive_line(
    polyline: list[tuple[float, float]], diagram: dict[str, Any]
) -> list[tuple[float, float]]:
    best = polyline
    best_d = 45.0
    for pl in _diagram_primitives_lines(diagram):
        d = _polyline_match_score(polyline, pl)
        if d < best_d:
            best_d = d
            best = pl
    return best


def _label_anchor_on_line(
    polyline: list[tuple[float, float]], label_box: BBoxPx | None
) -> tuple[float, float]:
    if not label_box:
        return polyline[0]
    return min(_sample_polyline(polyline, step=6.0), key=lambda p: _dist_to_box(p, label_box))


def _body_endpoint(
    polyline: list[tuple[float, float]], label_anchor: tuple[float, float]
) -> tuple[float, float]:
    return max(polyline, key=lambda p: _dist(p, label_anchor))


def _bbox_from_points(pts: list[tuple[float, float]]) -> BBoxPx:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x, y = min(xs), min(ys)
    return BBoxPx(x=x, y=y, w=max(8.0, max(xs) - x), h=max(8.0, max(ys) - y))


def _oriented_component_polygon(
    body: tuple[float, float],
    label_anchor: tuple[float, float],
    leader_len: float,
) -> list[tuple[float, float]]:
    """Elongated quad aligned with leader (paddle/antenna), not a square."""
    dx = body[0] - label_anchor[0]
    dy = body[1] - label_anchor[1]
    length = max(leader_len, 1.0)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    along = max(22.0, min(65.0, length * 0.38))
    perp = max(14.0, min(52.0, length * 0.32))
    back = (body[0] - ux * along, body[1] - uy * along)
    return [
        (back[0] + px * perp, back[1] + py * perp),
        (back[0] - px * perp, back[1] - py * perp),
        (body[0] - px * perp * 0.55, body[1] - py * perp * 0.55),
        (body[0] + px * perp * 0.55, body[1] + py * perp * 0.55),
    ]


def _extract_contour_polygon(
    png_bytes: bytes,
    body: tuple[float, float],
    label_anchor: tuple[float, float],
    *,
    img_w: float,
    img_h: float,
) -> list[tuple[float, float]] | None:
    """Trace ink blob at leader tip (satellite component outline)."""
    import cv2
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    leader_len = _dist(body, label_anchor)
    radius = int(max(28, min(95, leader_len * 0.55)))
    bx, by = int(body[0]), int(body[1])
    x0 = max(0, bx - radius)
    y0 = max(0, by - radius)
    x1 = min(binary.shape[1], bx + radius)
    y1 = min(binary.shape[0], by + radius)
    roi = binary[y0:y1, x0:x1].copy()
    if roi.size == 0:
        return None

    lx = int(label_anchor[0]) - x0
    ly = int(label_anchor[1]) - y0
    bx_l = bx - x0
    by_l = by - y0
    cv2.line(roi, (lx, ly), (bx_l, by_l), 0, 2)

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    roi_c = (bx_l, by_l)
    best_cnt = None
    best_rank = 1e9
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < 120 or area > 25000:
            continue
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw < 6 or ch < 6:
            continue
        aspect = max(cw, ch) / max(min(cw, ch), 1)
        if aspect > 9:
            continue
        m = cv2.moments(cnt)
        if m["m00"] <= 0:
            continue
        cx = m["m10"] / m["m00"]
        cy = m["m01"] / m["m00"]
        rank = _dist((cx, cy), roi_c) - min(area, 8000) * 0.01
        if rank < best_rank:
            best_rank = rank
            best_cnt = cnt

    if best_cnt is None:
        return None

    peri = cv2.arcLength(best_cnt, True)
    approx = cv2.approxPolyDP(best_cnt, max(1.5, 0.02 * peri), True)
    pts = [(float(p[0][0] + x0), float(p[0][1] + y0)) for p in approx]
    if len(pts) < 3:
        return None
    bb = _bbox_from_points(pts)
    if _is_huge_bbox(bb, img_w, img_h, max_frac=0.12):
        return None
    return pts


def _nearby_cv_polygon(
    pt: tuple[float, float],
    cv_boxes: list[tuple[BBoxPx, float]],
    *,
    max_dist: float = 55.0,
) -> list[tuple[float, float]] | None:
    bb = _nearby_cv_bbox(pt, cv_boxes, max_dist=max_dist)
    if not bb:
        return None
    aspect = bb.w / max(bb.h, 1)
    if aspect > 4.5:
        return _oriented_component_polygon(
            (bb.x + bb.w, bb.y + bb.h / 2),
            (bb.x, bb.y + bb.h / 2),
            bb.w,
        )
    if aspect < 0.22:
        return _oriented_component_polygon(
            (bb.x + bb.w / 2, bb.y + bb.h),
            (bb.x + bb.w / 2, bb.y),
            bb.h,
        )
    x, y, w, h = bb.x, bb.y, bb.w, bb.h
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _nearby_cv_bbox(
    pt: tuple[float, float],
    cv_boxes: list[tuple[BBoxPx, float]],
    *,
    max_dist: float = 70.0,
) -> BBoxPx | None:
    best: tuple[float, BBoxPx] | None = None
    for bb, _score in cv_boxes:
        if _is_text_like_box(bb):
            continue
        d = _dist(_center(bb), pt)
        if d > max_dist:
            continue
        if best is None or d < best[0]:
            best = (d, bb)
    return best[1] if best else None


def _component_shape(
    png_bytes: bytes,
    body: tuple[float, float],
    label_anchor: tuple[float, float],
    leader_len: float,
    cv_boxes: list[tuple[BBoxPx, float]],
    img_w: float,
    img_h: float,
) -> list[tuple[float, float]]:
    traced = _extract_contour_polygon(
        png_bytes, body, label_anchor, img_w=img_w, img_h=img_h
    )
    if traced and len(traced) >= 3:
        return traced
    cv_poly = _nearby_cv_polygon(body, cv_boxes)
    if cv_poly:
        return cv_poly
    return _oriented_component_polygon(body, label_anchor, leader_len)


def _vectors_for_component(
    leader: list[tuple[float, float]],
    shape_pts: list[tuple[float, float]],
    name: str,
) -> list[AnnotationVector]:
    vecs: list[AnnotationVector] = []
    if len(leader) >= 2:
        kind: str = "line" if len(leader) == 2 else "polyline"
        vecs.append(
            AnnotationVector(
                id=str(uuid.uuid4()),
                kind=kind,  # type: ignore[arg-type]
                points=[(float(x), float(y)) for x, y in leader],
                auto=True,
                label=None,
            )
        )
    if len(shape_pts) >= 3:
        vecs.append(
            AnnotationVector(
                id=str(uuid.uuid4()),
                kind="polygon",
                points=[(float(x), float(y)) for x, y in shape_pts],
                auto=True,
                label=name,
            )
        )
    return vecs


def _assign_bboxes_from_leader_lines(
    parts: list[PartAnnotation],
    diagram: dict[str, Any],
    ocr: list[tuple[str, BBoxPx, float]],
    cv_boxes: list[tuple[BBoxPx, float]],
    png_bytes: bytes,
    img_w: float,
    img_h: float,
) -> None:
    """Use diagram leader lines (label → component) to place per-part overlays."""
    nodes = {str(n.get("id")): n for n in diagram.get("nodes") or [] if n.get("id")}
    incident: dict[str, list[tuple[dict[str, Any], list[tuple[float, float]], str]]] = (
        defaultdict(list)
    )
    for edge in diagram.get("edges") or []:
        pl = _polyline_points(edge)
        if len(pl) < 2:
            continue
        src, tgt = str(edge.get("source") or ""), str(edge.get("target") or "")
        if src:
            incident[src].append((edge, pl, "source"))
        if tgt:
            incident[tgt].append((edge, pl, "target"))

    hub_ids = {nid for nid, edges in incident.items() if len(edges) >= 4}

    part_by_node = {p.node_id: p for p in parts if p.node_id}

    for nid, node in nodes.items():
        part = part_by_node.get(nid)
        if not part or not part.auto_detected:
            continue
        if nid in hub_ids:
            part.bbox = None
            part.vectors = []
            continue
        if not _is_component_label(part.name):
            continue

        label_box = _find_ocr_box_for_name(part.name, ocr)

        best_pl: list[tuple[float, float]] | None = None
        best_len = 0.0
        for _edge, pl, _role in incident.get(nid, []):
            merged = _merge_with_primitive_line(pl, diagram)
            anchor = _label_anchor_on_line(merged, label_box)
            body = _body_endpoint(merged, anchor)
            length = _dist(anchor, body)
            if length > best_len:
                best_len = length
                best_pl = merged

        if not best_pl or best_len < 18:
            continue

        label_anchor = _label_anchor_on_line(best_pl, label_box)
        body_pt = _body_endpoint(best_pl, label_anchor)
        shape_pts = _component_shape(
            png_bytes, body_pt, label_anchor, best_len, cv_boxes, img_w, img_h
        )
        part.bbox = _expand_bbox(
            _bbox_from_points(shape_pts), pad=2, max_w=img_w, max_h=img_h
        )
        part.vectors = _vectors_for_component(best_pl, shape_pts, part.name)


def _polyline_length(pl: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(1, len(pl)):
        total += _dist(pl[i - 1], pl[i])
    return total


def _cv_component_boxes(png_bytes: bytes) -> list[tuple[BBoxPx, float]]:
    """Large closed shapes from classical CV (symbols/blocks, not captions)."""
    try:
        from schemagraph.cv.primitives import detect_primitives
    except Exception:
        return []

    layer = detect_primitives(png_bytes)
    out: list[tuple[BBoxPx, float]] = []
    for sh in layer.shapes:
        if sh.kind not in ("rect", "circle", "polyline"):
            continue
        if not sh.bbox or sh.bbox.w < 20 or sh.bbox.h < 20:
            continue
        bb = BBoxPx(x=sh.bbox.x, y=sh.bbox.y, w=sh.bbox.w, h=sh.bbox.h)
        if _is_text_like_box(bb):
            continue
        if sh.bbox.w * sh.bbox.h < 1200:
            continue
        out.append((bb, float(sh.score)))
    return out


def _cv_component_boxes_filtered(
    png_bytes: bytes, img_w: float, img_h: float
) -> list[tuple[BBoxPx, float]]:
    return [
        (bb, sc)
        for bb, sc in _cv_component_boxes(png_bytes)
        if not _is_huge_bbox(bb, img_w, img_h)
    ]


def _best_ocr_name_for_part(
    part_bbox: BBoxPx,
    ocr: list[tuple[str, BBoxPx, float]],
    *,
    max_dist: float = 120.0,
) -> str | None:
    """Pick caption text associated with a component (inside or just above the box)."""
    pc = _center(part_bbox)
    best: tuple[float, str] | None = None

    for name, tbox, conf in ocr:
        tc = _center(tbox)
        inside = (
            tbox.x >= part_bbox.x - 8
            and tbox.y >= part_bbox.y - 8
            and tbox.x + tbox.w <= part_bbox.x + part_bbox.w + 8
            and tbox.y + tbox.h <= part_bbox.y + part_bbox.h + 8
        )
        above = (
            abs(tc[0] - pc[0]) < part_bbox.w * 0.6
            and part_bbox.y - tbox.y - tbox.h < 48
            and tbox.y + tbox.h <= part_bbox.y + 12
        )
        if not inside and not above:
            d = _dist(tc, pc)
            if d > max_dist:
                continue
        else:
            d = _dist(tc, pc) * 0.35

        score = d - conf * 40
        if best is None or score < best[0]:
            best = (score, name)

    return best[1] if best else None


def _match_nodes_to_cv(
    parts: list[PartAnnotation],
    cv_boxes: list[tuple[BBoxPx, float]],
    ocr: list[tuple[str, BBoxPx, float]],
    img_w: float,
    img_h: float,
) -> None:
    """Assign diagram nodes without bbox to CV component shapes (matched by OCR name)."""
    assigned_cv: set[int] = set()

    for part in parts:
        if part.bbox or not part.node_id:
            continue
        node_hint = part.name.lower()
        best_i: int | None = None
        best_rank = 1e9
        for i, (bb, score) in enumerate(cv_boxes):
            if i in assigned_cv or _is_text_like_box(bb):
                continue
            ocr_name = _best_ocr_name_for_part(bb, ocr, max_dist=80)
            rank = 500.0 - score * 50.0
            if ocr_name:
                low = ocr_name.lower()
                if low == node_hint or node_hint in low or low in node_hint:
                    rank = 0.0
                else:
                    rank = min(rank, 40.0)
            if rank < best_rank:
                best_rank = rank
                best_i = i

        if best_i is not None:
            bb = _expand_bbox(cv_boxes[best_i][0], pad=4, max_w=img_w, max_h=img_h)
            part.bbox = bb
            part.vectors = _auto_vectors_for_bbox(bb, part.name)
            assigned_cv.add(best_i)


def _apply_ocr_names(parts: list[PartAnnotation], ocr: list[tuple[str, BBoxPx, float]]) -> None:
    for part in parts:
        if not part.bbox:
            continue
        if not part.auto_detected:
            continue
        ocr_name = _best_ocr_name_for_part(part.bbox, ocr)
        if ocr_name:
            part.name = ocr_name
            if part.vectors:
                for v in part.vectors:
                    if v.auto:
                        v.label = ocr_name


def _add_cv_components(
    parts: list[PartAnnotation],
    cv_boxes: list[tuple[BBoxPx, float]],
    ocr: list[tuple[str, BBoxPx, float]],
    img_w: float,
    img_h: float,
) -> list[PartAnnotation]:
    """Add CV-detected symbols not already covered by a diagram node."""
    out = list(parts)
    for bb, _score in cv_boxes:
        if _is_text_like_box(bb) or _is_huge_bbox(bb, img_w, img_h):
            continue
        expanded = _expand_bbox(bb, pad=4, max_w=img_w, max_h=img_h)
        if any(p.bbox and _iou(p.bbox, expanded) > 0.35 for p in out):
            continue
        name = _best_ocr_name_for_part(expanded, ocr) or _infer_name_from_neighbors(expanded, ocr)
        if not name or is_axis_reference_label(name):
            continue
        out.append(
            PartAnnotation(
                id=str(uuid.uuid4()),
                node_id=None,
                name=name,
                auto_detected=True,
                bbox=expanded,
                vectors=_auto_vectors_for_bbox(expanded, name),
                extra={"source": "cv"},
            )
        )
    return out


def _infer_name_from_neighbors(bb: BBoxPx, ocr: list[tuple[str, BBoxPx, float]]) -> str | None:
    pc = _center(bb)
    best: tuple[float, str] | None = None
    for name, tbox, conf in ocr:
        d = _dist(_center(tbox), pc)
        if d > 150:
            continue
        if best is None or d < best[0]:
            best = (d, name)
    return best[1] if best else None


def auto_detect_annotations(
    png_bytes: bytes,
    diagram: dict[str, Any] | None,
    existing: list[PartAnnotation] | None = None,
) -> list[PartAnnotation]:
    """Components from AI diagram + CV shapes; OCR only names them (no label-as-part)."""
    import io

    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        w, h = img.size

    parts = seed_from_diagram(diagram or {"nodes": []}, existing)
    ocr = _ocr_labels_only(png_bytes)
    img_w, img_h = float(w), float(h)
    cv_boxes = _cv_component_boxes_filtered(png_bytes, img_w, img_h)

    _assign_bboxes_from_leader_lines(
        parts, diagram or {}, ocr, cv_boxes, png_bytes, img_w, img_h
    )
    _match_nodes_to_cv(parts, cv_boxes, ocr, img_w, img_h)
    _apply_ocr_names(parts, ocr)

    for p in parts:
        if p.bbox and not p.vectors:
            p.vectors = _auto_vectors_for_bbox(p.bbox, p.name)

    parts = _add_cv_components(parts, cv_boxes, ocr, img_w, img_h)

    # Drop parts that are only tiny text boxes with no real component
    filtered: list[PartAnnotation] = []
    for p in parts:
        if p.bbox and _is_text_like_box(p.bbox) and not p.node_id:
            continue
        if p.bbox and _is_huge_bbox(p.bbox, img_w, img_h):
            continue
        if p.name.lower() in _BAD_NAMES:
            continue
        if is_axis_reference_label(p.name):
            continue
        if p.node_id and p.node_id in {
            nid
            for nid, edges in _edge_incident_index(diagram or {}).items()
            if len(edges) >= 4
        }:
            continue
        filtered.append(p)

    return filtered


def _edge_incident_index(
    diagram: dict[str, Any],
) -> dict[str, list[tuple[dict[str, Any], list[tuple[float, float]], str]]]:
    incident: dict[str, list[tuple[dict[str, Any], list[tuple[float, float]], str]]] = (
        defaultdict(list)
    )
    for edge in diagram.get("edges") or []:
        pl = _polyline_points(edge)
        if len(pl) < 2:
            continue
        src, tgt = str(edge.get("source") or ""), str(edge.get("target") or "")
        if src:
            incident[src].append((edge, pl, "source"))
        if tgt:
            incident[tgt].append((edge, pl, "target"))
    return incident
