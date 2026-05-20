"""High-level functional facade over the package.

These functions are what library callers should use; the CLI is a thin
wrapper over them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from schemagraph.config import get_settings
from schemagraph.export.base import load_exporter
from schemagraph.ingest.loaders import load_input
from schemagraph.ir import ids as _ids
from schemagraph.ir.builder import IRBuilder
from schemagraph.ir.schema import Diagram, PrimitiveLayer
from schemagraph.ir.validate import ValidationReport, validate_diagram
from schemagraph.physics.parametric import apply_parameters, sweep
from schemagraph.vlm.base import ExtractionRequest, load_provider


def parse(
    path: Union[str, Path],
    *,
    provider: Optional[str] = None,
    domain: Optional[str] = None,
    page: int = 1,
    run_cv: bool = True,
    run_ocr: bool = True,
    prompt_variant: str = "default",
    handdrawn: bool = False,
    provider_kwargs: Optional[dict] = None,
) -> Diagram:
    """End-to-end parse of an input file into a validated :class:`Diagram`.

    The function:
    1. Loads + normalizes the input. If ``handdrawn=True``, uses the
       hand-drawn-friendly preprocessor (adaptive thresholding, perspective
       correction, optional skeletonization) and switches to the
       ``"handdrawn"`` prompt variant by default.
    2. Optionally runs classical CV (lines/shapes/junctions) and OCR.
    3. Calls the named VLM provider with the image + structural hints.
    4. Fuses CV primitives and VLM semantics into a Diagram.
    """
    settings = get_settings()
    provider_name = provider or settings.default_provider
    provider_kwargs = provider_kwargs or {}

    loaded = load_input(path, page=page)
    primitives: Optional[PrimitiveLayer] = None
    if run_cv:
        from schemagraph.cv.primitives import detect_primitives
        from schemagraph.ingest.normalize import NormalizedRaster, normalize_raster

        if handdrawn:
            from schemagraph.cv.handdrawn import prepare_handdrawn

            prep = prepare_handdrawn(
                loaded.png_bytes, max_dim_px=settings.cv_max_image_dim_px
            )
            normalized = NormalizedRaster(
                gray=prep.gray, rgb=prep.rgb, binary=prep.binary, scale=1.0, rotation_deg=0.0
            )
        else:
            normalized = normalize_raster(
                loaded.png_bytes, max_dim_px=settings.cv_max_image_dim_px
            )
        diagram_id = _ids.diagram_id(loaded.source.sha256, page=page)
        primitives = detect_primitives(
            loaded.png_bytes, diagram_id=diagram_id, normalized=normalized
        )
        if run_ocr:
            from schemagraph.cv.ocr import detect_text_spans

            primitives.text_spans = detect_text_spans(normalized.gray)
    else:
        diagram_id = _ids.diagram_id(loaded.source.sha256, page=page)

    if handdrawn and prompt_variant == "default":
        prompt_variant = "handdrawn"

    vlm = load_provider(provider_name, **provider_kwargs)
    response = vlm.extract(
        ExtractionRequest(
            image_bytes=loaded.png_bytes,
            mime="image/png",
            primitives=primitives,
            domain_hint=domain,
            prompt_variant=prompt_variant,
        )
    )
    payload = dict(response.payload)
    payload["_producer"] = f"{response.provider}:{response.model}"

    builder = IRBuilder(
        snap_radius_px=settings.fusion_snap_radius_px,
        edge_support_radius_px=settings.fusion_edge_support_radius_px,
    )
    diagram = builder.build(
        source=loaded.source,
        diagram_id=diagram_id,
        vlm_payload=payload,
        primitives=primitives,
        domain=domain,
    )
    return diagram


def validate(diagram: Diagram) -> ValidationReport:
    """Run cross-field IR validation on a Diagram."""
    return validate_diagram(diagram)


def annotate(diagram: Diagram, *, domain: str = "generic", **kwargs: Any) -> Diagram:
    """Apply a physics annotator (units, equations, parametric placeholders) to a Diagram."""
    from schemagraph.physics.annotators import load_annotator

    annotator = load_annotator(domain, **kwargs)
    return annotator.annotate(diagram)


def export(
    diagram: Diagram,
    *,
    format: str,
    path: Optional[Union[str, Path]] = None,
    **options: Any,
):
    """Export a Diagram via the named exporter plugin."""
    exporter = load_exporter(format)
    if path is not None:
        return exporter.write(diagram, path, **options)
    return exporter.export(diagram, **options)


__all__ = ["parse", "annotate", "validate", "export", "apply_parameters", "sweep"]
