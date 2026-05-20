"""Fuse classical-CV primitives with VLM semantic output into a validated Diagram.

The fusion logic intentionally treats CV primitives as the source of pixel
truth, and the VLM as the source of *semantics*. When the two disagree we
prefer pixel-grounded geometry and downgrade hallucinated VLM edges that
have no pixel support, while still keeping high-confidence VLM-only nodes
(e.g. components recognized from labels but not cleanly segmented).
"""

from __future__ import annotations

import math
from typing import Iterable

from schemagraph.ir import ids as _ids
from schemagraph.ir.schema import (
    BBox,
    Diagram,
    Edge,
    GeometryRef,
    Node,
    Port,
    PrimitiveLayer,
    PrimitiveShape,
    Provenance,
    SourceMeta,
)


# ---------------------------------------------------------------------------
# small geometry helpers
# ---------------------------------------------------------------------------


def _bbox_center(bbox: BBox) -> tuple[float, float]:
    return (bbox.x + bbox.w / 2.0, bbox.y + bbox.h / 2.0)


def _polyline_length(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _min_distance_to_polyline(
    p: tuple[float, float], poly: list[tuple[float, float]]
) -> float:
    px, py = p
    best = float("inf")
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq == 0:
            d = math.hypot(px - x0, py - y0)
        else:
            t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / seg_len_sq))
            proj = (x0 + t * dx, y0 + t * dy)
            d = math.hypot(px - proj[0], py - proj[1])
        if d < best:
            best = d
    return best


# ---------------------------------------------------------------------------
# fusion
# ---------------------------------------------------------------------------


class IRBuilder:
    """Construct a :class:`Diagram` from VLM semantic output and CV primitives.

    Parameters
    ----------
    snap_radius_px:
        Maximum distance in pixels for a VLM-reported node center to be
        snapped to a CV-detected shape's center, or for an edge endpoint to
        be considered to "lie on" a CV polyline.
    edge_support_radius_px:
        Maximum distance from the VLM-predicted edge polyline (or straight
        line between endpoints if no polyline was given) to a CV-detected
        line for the edge to be considered pixel-supported.
    """

    def __init__(
        self,
        snap_radius_px: float = 18.0,
        edge_support_radius_px: float = 12.0,
        min_node_confidence: float = 0.2,
        min_edge_confidence: float = 0.2,
    ) -> None:
        self.snap_radius_px = snap_radius_px
        self.edge_support_radius_px = edge_support_radius_px
        self.min_node_confidence = min_node_confidence
        self.min_edge_confidence = min_edge_confidence

    # ------------------------------------------------------------------
    def build(
        self,
        *,
        source: SourceMeta,
        diagram_id: str,
        vlm_payload: dict,
        primitives: PrimitiveLayer | None,
        domain: str | None = None,
    ) -> Diagram:
        """Build a Diagram from a (possibly raw) VLM JSON payload + CV primitives."""

        nodes_in = vlm_payload.get("nodes", []) or []
        edges_in = vlm_payload.get("edges", []) or []
        constraints_in = vlm_payload.get("constraints", []) or []
        equations_in = vlm_payload.get("equations", []) or []
        datasets_in = vlm_payload.get("datasets", []) or []
        parameters_in = vlm_payload.get("parameters", []) or []

        prov_vlm = Provenance(stage="vlm", producer=vlm_payload.get("_producer", "vlm:unknown"))
        prov_fusion = Provenance(stage="fusion", producer="schemagraph.ir.builder.IRBuilder")

        shapes = primitives.shapes if primitives else []
        polylines = [s for s in shapes if s.kind in {"line", "polyline"} and s.points]

        # ------------- nodes ------------------------------------------
        nodes: list[Node] = []
        node_anchor_to_id: dict[str, str] = {}
        used_shape_ids: set[str] = set()

        for raw in nodes_in:
            conf = float(raw.get("confidence", 0.8))
            if conf < self.min_node_confidence:
                continue
            kind = str(raw.get("kind", "component"))
            label = raw.get("label")
            anchor = self._coerce_point(raw.get("anchor") or raw.get("position"))
            shape, snapped = self._snap_to_shape(anchor, shapes, used_shape_ids)
            if shape is not None:
                used_shape_ids.add(shape.id)
            geom = self._geometry_for(shape, raw)
            anchor_for_id = snapped or anchor
            nid = _ids.node_id(diagram_id, kind, anchor_for_id, label)
            ports = self._build_ports(nid, raw.get("ports", []) or [])
            nodes.append(
                Node(
                    id=nid,
                    kind=kind,
                    label=label,
                    properties=self._coerce_properties(raw.get("properties")),
                    ports=ports,
                    geometry=geom,
                    domain=raw.get("domain") or domain,
                    provenance=prov_fusion if shape is not None else prov_vlm,
                    confidence=conf,
                    tags=list(raw.get("tags") or []),
                )
            )
            local_key = raw.get("id") or raw.get("local_id")
            if local_key is not None:
                node_anchor_to_id[str(local_key)] = nid

        # ------------- edges ------------------------------------------
        node_index = {n.id: n for n in nodes}
        port_index = {p.id: p for n in nodes for p in n.ports}

        edges: list[Edge] = []
        for raw in edges_in:
            conf = float(raw.get("confidence", 0.8))
            src_key = str(raw.get("source"))
            dst_key = str(raw.get("target"))
            src = node_anchor_to_id.get(src_key, src_key)
            dst = node_anchor_to_id.get(dst_key, dst_key)
            if src not in node_index and src not in port_index:
                continue
            if dst not in node_index and dst not in port_index:
                continue
            polyline = self._coerce_polyline(raw.get("polyline") or raw.get("polyline_px"))
            supported, snapped_poly = self._edge_pixel_support(
                src, dst, polyline, node_index, port_index, polylines
            )
            if not supported:
                conf *= 0.5
            if conf < self.min_edge_confidence:
                continue
            eid = _ids.edge_id(diagram_id, src, dst, snapped_poly)
            # Strip phantom port references VLMs sometimes invent (e.g.
            # "input"/"output") when the node has no explicit Ports modeled.
            sp_raw = raw.get("source_port")
            tp_raw = raw.get("target_port")
            sp = sp_raw if sp_raw in port_index else None
            tp = tp_raw if tp_raw in port_index else None
            edges.append(
                Edge(
                    id=eid,
                    source=src,
                    target=dst,
                    source_port=sp,
                    target_port=tp,
                    kind=str(raw.get("kind", "edge")),
                    label=raw.get("label"),
                    directed=bool(raw.get("directed", False)),
                    properties=self._coerce_properties(raw.get("properties")),
                    polyline_px=snapped_poly,
                    domain=raw.get("domain") or domain,
                    provenance=prov_fusion if supported else prov_vlm,
                    confidence=min(1.0, conf),
                )
            )

        # ------------- pass-through constraints/equations/datasets/params --
        constraints = self._build_constraints(diagram_id, constraints_in, prov_vlm)
        equations = self._build_equations(diagram_id, equations_in, prov_vlm)
        datasets = self._build_datasets(diagram_id, datasets_in, prov_vlm)
        parameters = self._build_parameters(diagram_id, parameters_in)

        return Diagram(
            id=diagram_id,
            source=source,
            nodes=nodes,
            edges=edges,
            constraints=constraints,
            equations=equations,
            datasets=datasets,
            parameters=parameters,
            primitives=primitives,
            domain=domain or vlm_payload.get("domain"),
            metadata={"vlm_model": vlm_payload.get("_producer")},
        )

    # ------------------------------------------------------------------
    def _coerce_point(self, p) -> tuple[float, float] | None:
        if p is None:
            return None
        if isinstance(p, dict):
            if "x" in p and "y" in p:
                return (float(p["x"]), float(p["y"]))
            return None
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return (float(p[0]), float(p[1]))
        return None

    def _coerce_polyline(self, poly) -> list[tuple[float, float]] | None:
        if not poly:
            return None
        out: list[tuple[float, float]] = []
        for p in poly:
            pt = self._coerce_point(p)
            if pt is not None:
                out.append(pt)
        return out or None

    def _coerce_properties(self, props) -> dict:
        if not props:
            return {}
        if isinstance(props, dict):
            return props
        return {}

    def _snap_to_shape(
        self,
        anchor: tuple[float, float] | None,
        shapes: Iterable[PrimitiveShape],
        used: set[str],
    ) -> tuple[PrimitiveShape | None, tuple[float, float] | None]:
        if anchor is None:
            return None, None
        ax, ay = anchor
        best: PrimitiveShape | None = None
        best_d = self.snap_radius_px
        for s in shapes:
            if s.id in used:
                continue
            if s.kind not in {"rect", "circle", "ellipse"}:
                continue
            if s.bbox is None:
                continue
            cx, cy = _bbox_center(s.bbox)
            d = math.hypot(cx - ax, cy - ay)
            if d < best_d:
                best_d = d
                best = s
        if best is not None and best.bbox is not None:
            return best, _bbox_center(best.bbox)
        return None, None

    def _geometry_for(self, shape: PrimitiveShape | None, raw: dict) -> GeometryRef | None:
        if shape is not None and shape.bbox is not None:
            return GeometryRef(
                bbox=shape.bbox,
                polyline_px=shape.points,
                rotation_deg=float(shape.attrs.get("rotation_deg", 0.0)),
            )
        bbox = raw.get("bbox")
        if isinstance(bbox, dict) and {"x", "y", "w", "h"}.issubset(bbox.keys()):
            return GeometryRef(bbox=BBox(**{k: float(bbox[k]) for k in ("x", "y", "w", "h")}))
        return None

    def _build_ports(self, node_id: str, ports_raw: list) -> list[Port]:
        ports: list[Port] = []
        for raw in ports_raw:
            role = raw.get("role")
            position = self._coerce_point(raw.get("position") or raw.get("position_px"))
            pid = _ids.port_id(node_id, role, position)
            ports.append(
                Port(
                    id=pid,
                    node_id=node_id,
                    role=role,
                    position_px=position,
                    direction=raw.get("direction"),
                    properties=self._coerce_properties(raw.get("properties")),
                )
            )
        return ports

    def _edge_pixel_support(
        self,
        src: str,
        dst: str,
        polyline: list[tuple[float, float]] | None,
        node_index: dict[str, Node],
        port_index: dict[str, Port],
        cv_polylines: list[PrimitiveShape],
    ) -> tuple[bool, list[tuple[float, float]] | None]:
        if not cv_polylines:
            return False, polyline

        def _anchor_for(key: str) -> tuple[float, float] | None:
            if key in port_index and port_index[key].position_px is not None:
                return port_index[key].position_px
            if key in node_index:
                geom = node_index[key].geometry
                if geom and geom.bbox:
                    return _bbox_center(geom.bbox)
            return None

        if polyline is None:
            a = _anchor_for(src)
            b = _anchor_for(dst)
            if a is None or b is None:
                return False, None
            polyline = [a, b]

        if _polyline_length(polyline) <= 0:
            return False, polyline

        # Walk the polyline mid-points; require any sample to be near a CV line.
        samples = []
        for (x0, y0), (x1, y1) in zip(polyline, polyline[1:]):
            samples.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0))
        if not samples:
            return False, polyline

        supported_count = 0
        for sample in samples:
            for s in cv_polylines:
                pts = s.points or []
                if len(pts) < 2:
                    continue
                if _min_distance_to_polyline(sample, pts) <= self.edge_support_radius_px:
                    supported_count += 1
                    break
        return supported_count / max(1, len(samples)) >= 0.5, polyline

    def _build_constraints(self, diagram_id: str, raw_list: list, prov: Provenance):
        from schemagraph.ir.schema import Constraint, Quantity

        out = []
        for raw in raw_list:
            kind = str(raw.get("kind", "equal"))
            targets = [str(t) for t in raw.get("targets", [])]
            expression = raw.get("expression")
            value_raw = raw.get("value")
            value = None
            if isinstance(value_raw, dict) and "value" in value_raw:
                value = Quantity(**value_raw)
            cid = _ids.constraint_id(diagram_id, kind, targets, expression)
            out.append(
                Constraint(
                    id=cid,
                    kind=kind,
                    targets=targets,
                    expression=expression,
                    value=value,
                    provenance=prov,
                )
            )
        return out

    def _build_equations(self, diagram_id: str, raw_list: list, prov: Provenance):
        from schemagraph.ir.schema import Equation

        out = []
        for raw in raw_list:
            text = str(raw.get("raw") or raw.get("text") or "")
            if not text:
                continue
            eid = _ids.equation_id(diagram_id, text)
            out.append(
                Equation(
                    id=eid,
                    raw=text,
                    sympy_repr=raw.get("sympy_repr"),
                    lhs=raw.get("lhs"),
                    rhs=raw.get("rhs"),
                    variables=dict(raw.get("variables") or {}),
                    provenance=prov,
                )
            )
        return out

    def _build_datasets(self, diagram_id: str, raw_list: list, prov: Provenance):
        from schemagraph.ir.schema import Dataset, DatasetSeries

        out = []
        for raw in raw_list:
            name = raw.get("name")
            axes = list(raw.get("axes") or [])
            series_raw = raw.get("series") or []
            series = [DatasetSeries(name=str(s.get("name", "")), values=list(s.get("values") or [])) for s in series_raw]
            did = _ids.dataset_id(diagram_id, name, axes)
            out.append(Dataset(id=did, name=name, axes=axes, series=series, provenance=prov))
        return out

    def _build_parameters(self, diagram_id: str, raw_list: list):
        from schemagraph.ir.schema import Parameter, Quantity

        out = []
        for raw in raw_list:
            name = str(raw.get("name"))
            default = raw.get("default")
            default_q = Quantity(**default) if isinstance(default, dict) else None
            bounds = raw.get("bounds")
            bounds_t = tuple(bounds) if isinstance(bounds, (list, tuple)) and len(bounds) == 2 else None
            pid = _ids.parameter_id(diagram_id, name)
            out.append(
                Parameter(
                    id=pid,
                    name=name,
                    default=default_q,
                    bounds=bounds_t,
                    description=raw.get("description"),
                    targets=[str(t) for t in raw.get("targets", [])],
                )
            )
        return out
