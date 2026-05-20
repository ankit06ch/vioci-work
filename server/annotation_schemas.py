"""Pydantic schemas for schematic part annotations (vectors + physical properties)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BBoxPx(BaseModel):
    x: float
    y: float
    w: float
    h: float


class AnnotationVector(BaseModel):
    id: str
    kind: Literal["line", "polyline", "rect", "arrow", "polygon"] = "line"
    points: list[tuple[float, float]] = Field(default_factory=list)
    auto: bool = False
    label: str | None = None


class PartAnnotation(BaseModel):
    id: str
    node_id: str | None = None
    name: str
    auto_detected: bool = False
    bbox: BBoxPx | None = None
    vectors: list[AnnotationVector] = Field(default_factory=list)
    mass_kg: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    volume_m3: float | None = None
    material: str | None = None
    power_w: float | None = None
    notes: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AnnotationsDocument(BaseModel):
    annotations: list[PartAnnotation] = Field(default_factory=list)
    image_enhanced: bool = False
    image_quality_score: float | None = None


class AnnotationsUpdate(BaseModel):
    annotations: list[PartAnnotation]


class EnhanceImageResult(BaseModel):
    enhanced: bool
    quality_score: float
    message: str
