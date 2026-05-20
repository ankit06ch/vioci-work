"""Canonical Intermediate Representation (IR) for schemagraph.

This module defines the strongly-typed, validated data structures that every
pipeline stage either produces or consumes. The IR is intentionally
domain-agnostic: physics specificity lives in unit-aware ``properties`` and in
domain annotators, not in the schema itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Primitive value types
# ---------------------------------------------------------------------------


class Quantity(BaseModel):
    """A unit-aware physical quantity.

    The value is stored as a plain float; the unit is a Pint-compatible string
    (e.g. ``"ohm"``, ``"newton * meter"``, ``"kilogram / second"``). ``raw``
    preserves the original token extracted from the diagram so downstream
    consumers can audit interpretation.
    """

    model_config = ConfigDict(frozen=False, extra="forbid")

    value: float
    unit: Optional[str] = None
    raw: Optional[str] = None
    uncertainty: Optional[float] = None

    def __str__(self) -> str:
        if self.unit:
            return f"{self.value} {self.unit}"
        return str(self.value)


PropertyValue = Union[Quantity, str, float, int, bool, list, dict, None]


class BBox(BaseModel):
    """Axis-aligned bounding box in pixel coordinates."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    w: float
    h: float

    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)


class Provenance(BaseModel):
    """Origin of an IR artifact for auditability."""

    model_config = ConfigDict(extra="forbid")

    stage: Literal["ingest", "cv", "vlm", "fusion", "annotator", "user", "import"]
    producer: str  # e.g. "openai:gpt-4o", "opencv:HoughLinesP", "ElectricalAnnotator"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class GeometryRef(BaseModel):
    """A reference to a geometric primitive backing a node or edge."""

    model_config = ConfigDict(extra="forbid")

    bbox: Optional[BBox] = None
    polyline_px: Optional[list[tuple[float, float]]] = None
    rotation_deg: float = 0.0
    svg_path: Optional[str] = None


class VectorPath(BaseModel):
    """A vector geometry path (line, polyline, polygon, arc, or SVG `d=` string)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["line", "polyline", "polygon", "circle", "arc", "path"]
    points: Optional[list[tuple[float, float]]] = None
    svg_d: Optional[str] = None
    closed: bool = False
    stroke_px: float = 1.0
    attrs: dict[str, Any] = Field(default_factory=dict)


class VectorLayer(BaseModel):
    """Vectorized geometry layer recovered from the input (or preserved if native SVG)."""

    model_config = ConfigDict(extra="forbid")

    width_px: float
    height_px: float
    paths: list[VectorPath] = Field(default_factory=list)
    source: Literal["native_svg", "raster_vectorized", "mixed"] = "raster_vectorized"


# ---------------------------------------------------------------------------
# Graph elements
# ---------------------------------------------------------------------------


class Port(BaseModel):
    """A typed attachment point on a node where edges may connect."""

    model_config = ConfigDict(extra="forbid")

    id: str
    node_id: str
    role: Optional[str] = None  # e.g. "anode", "inlet", "fixed_support", "in", "out"
    position_px: Optional[tuple[float, float]] = None
    direction: Optional[Literal["in", "out", "bidir", "neutral"]] = None
    properties: dict[str, PropertyValue] = Field(default_factory=dict)


class Node(BaseModel):
    """A component / vertex in the diagram."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str  # e.g. "resistor", "beam", "valve", "block", "vertex", "junction"
    label: Optional[str] = None
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    ports: list[Port] = Field(default_factory=list)
    geometry: Optional[GeometryRef] = None
    domain: Optional[str] = None  # "electrical", "mechanical", "fluid", "thermal", ...
    provenance: Provenance
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """A connection between two nodes (or ports)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: str  # node_id or port_id
    target: str
    source_port: Optional[str] = None
    target_port: Optional[str] = None
    kind: str = "edge"  # "wire", "rigid_link", "pipe", "signal", "graph_edge", ...
    label: Optional[str] = None
    directed: bool = False
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    polyline_px: Optional[list[tuple[float, float]]] = None
    domain: Optional[str] = None
    provenance: Provenance
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Constraint(BaseModel):
    """A semantic constraint binding properties of one or more graph elements."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str  # "equal", "dimension", "boundary_condition", "fixed", "inequality"
    targets: list[str]  # ids of nodes/edges/ports/parameters this constrains
    expression: Optional[str] = None  # sympy-parseable string
    value: Optional[Quantity] = None
    provenance: Provenance


class Equation(BaseModel):
    """An equation extracted from the diagram (e.g. legend annotations, free-floating math)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    raw: str
    sympy_repr: Optional[str] = None
    lhs: Optional[str] = None
    rhs: Optional[str] = None
    variables: dict[str, str] = Field(
        default_factory=dict
    )  # name -> property path "<node_id>.<prop>"
    provenance: Provenance


class DatasetSeries(BaseModel):
    """A single named series of values."""

    model_config = ConfigDict(extra="forbid")

    name: str
    values: list[float]


class Dataset(BaseModel):
    """Numerical data extracted from a plot/graph image."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: Optional[str] = None
    axes: list[str] = Field(default_factory=list)  # e.g. ["t (s)", "V (V)"]
    series: list[DatasetSeries] = Field(default_factory=list)
    provenance: Provenance


class Parameter(BaseModel):
    """A named, user-overridable parameter for downstream simulation/optimization."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    default: Optional[Quantity] = None
    bounds: Optional[tuple[float, float]] = None
    description: Optional[str] = None
    targets: list[str] = Field(default_factory=list)  # property paths this drives


# ---------------------------------------------------------------------------
# Source / pre-IR layers
# ---------------------------------------------------------------------------


class SourceMeta(BaseModel):
    """Information about the original input."""

    model_config = ConfigDict(extra="forbid")

    uri: Optional[str] = None
    sha256: Optional[str] = None
    mime: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    dpi: Optional[float] = None
    pages: int = 1
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TextSpan(BaseModel):
    """An OCR/text span detected on the input."""

    model_config = ConfigDict(extra="forbid")

    text: str
    bbox: BBox
    confidence: float = 1.0
    rotation_deg: float = 0.0


class PrimitiveShape(BaseModel):
    """A low-level CV-detected primitive (pre-semantic)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["line", "polyline", "rect", "circle", "ellipse", "arrow", "junction"]
    points: Optional[list[tuple[float, float]]] = None
    bbox: Optional[BBox] = None
    score: float = 1.0
    attrs: dict[str, Any] = Field(default_factory=dict)


class PrimitiveLayer(BaseModel):
    """Output of the classical-CV stage. Fed into VLMs as structural hints and used
    by the IR builder for pixel reconciliation."""

    model_config = ConfigDict(extra="forbid")

    width_px: int
    height_px: int
    shapes: list[PrimitiveShape] = Field(default_factory=list)
    text_spans: list[TextSpan] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level container
# ---------------------------------------------------------------------------


class Diagram(BaseModel):
    """A complete, validated diagram in normalized IR form."""

    model_config = ConfigDict(extra="forbid")

    id: str
    schema_version: str = "0.1.0"
    source: SourceMeta
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    equations: list[Equation] = Field(default_factory=list)
    datasets: list[Dataset] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    geometry_layer: Optional[VectorLayer] = None
    primitives: Optional[PrimitiveLayer] = None
    domain: Optional[str] = None  # primary detected/declared domain
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("nodes")
    @classmethod
    def _unique_node_ids(cls, v: list[Node]) -> list[Node]:
        ids = [n.id for n in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node ids")
        return v

    @field_validator("edges")
    @classmethod
    def _unique_edge_ids(cls, v: list[Edge]) -> list[Edge]:
        ids = [e.id for e in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate edge ids")
        return v

    def node_index(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}

    def port_index(self) -> dict[str, Port]:
        return {p.id: p for n in self.nodes for p in n.ports}
