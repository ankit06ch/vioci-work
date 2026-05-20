"""URDF / SDF exporter for mechanical-assembly diagrams.

Maps the IR's mechanical nodes (links / joints / masses / supports) and
rigid-link edges to a minimal URDF document. Edge kinds ``rigid_link``,
``revolute``, and ``prismatic`` become URDF joints. Geometry is recovered
from ``node.geometry.bbox`` when available; otherwise unit boxes are used.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram, Quantity


_LINK_KINDS = {"link", "beam", "mass", "joint", "rigid_body", "anchor", "support", "fixed_support", "roller"}
_JOINT_KIND_MAP = {
    "rigid_link": "fixed",
    "revolute": "revolute",
    "prismatic": "prismatic",
    "pin": "revolute",
    "slider": "prismatic",
}


class URDFExporter(Exporter):
    name = "urdf"
    default_extension = "urdf"
    binary = False

    def export(self, diagram: Diagram, *, robot_name: str | None = None, **options: Any) -> str:
        robot = ET.Element("robot", name=robot_name or f"diagram_{diagram.id}")

        # Links: every mechanical node becomes a link.
        for n in diagram.nodes:
            if n.kind not in _LINK_KINDS and n.domain not in {"mechanical", None}:
                continue
            link = ET.SubElement(robot, "link", name=_safe(n.id))
            inertial = ET.SubElement(link, "inertial")
            mass_val = _q_value(n.properties.get("mass"), default=1.0)
            ET.SubElement(inertial, "mass", value=f"{mass_val:g}")
            ET.SubElement(
                inertial,
                "inertia",
                ixx="1e-3", iyy="1e-3", izz="1e-3", ixy="0", ixz="0", iyz="0",
            )
            visual = ET.SubElement(link, "visual")
            geom = ET.SubElement(visual, "geometry")
            box = _bbox_or_unit(n)
            ET.SubElement(geom, "box", size=f"{box[0]:g} {box[1]:g} 0.01")

        # Joints: each edge becomes a joint between its two link endpoints.
        for e in diagram.edges:
            if e.kind not in _JOINT_KIND_MAP and e.domain not in {"mechanical", None}:
                continue
            jtype = _JOINT_KIND_MAP.get(e.kind, "fixed")
            joint = ET.SubElement(
                robot, "joint", name=_safe(e.id), type=jtype
            )
            ET.SubElement(joint, "parent", link=_safe(e.source))
            ET.SubElement(joint, "child", link=_safe(e.target))
            ET.SubElement(joint, "origin", xyz="0 0 0", rpy="0 0 0")
            if jtype in {"revolute", "prismatic"}:
                ET.SubElement(joint, "axis", xyz="0 0 1")
                ET.SubElement(joint, "limit", lower="-3.14159", upper="3.14159", effort="100", velocity="1")

        ET.indent(robot, space="  ")
        return '<?xml version="1.0"?>\n' + ET.tostring(robot, encoding="unicode")


def _safe(s: str) -> str:
    return s.replace(":", "_").replace("/", "_")


def _q_value(v, default: float = 0.0) -> float:
    if isinstance(v, Quantity):
        return float(v.value)
    if isinstance(v, (int, float)):
        return float(v)
    return default


def _bbox_or_unit(node) -> tuple[float, float]:
    if node.geometry and node.geometry.bbox:
        # convert from pixels to "design units"; pure-pixel-relative is fine for v1.
        return (max(0.05, node.geometry.bbox.w / 100.0), max(0.05, node.geometry.bbox.h / 100.0))
    return (0.1, 0.1)
