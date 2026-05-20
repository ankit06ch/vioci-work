"""Provider-agnostic multimodal extraction contract.

A :class:`VLMProvider` accepts an image (plus optional CV-derived structural
hints and OCR text spans) and returns a structured JSON payload conforming
to the *extraction schema* defined here. The IR builder then reconciles
that payload against CV primitives and produces a validated
:class:`schemagraph.ir.schema.Diagram`.

The extraction schema is intentionally a *subset* of the full IR schema —
we don't require the VLM to invent stable IDs, provenance, or pixel-grounded
geometry; those are filled in by the builder.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional

from schemagraph.ir.schema import PrimitiveLayer
from schemagraph.registry import provider_registry


@dataclass
class ExtractionRequest:
    """Input to a VLM provider."""

    image_bytes: bytes
    mime: str = "image/png"
    primitives: Optional[PrimitiveLayer] = None
    domain_hint: Optional[str] = None
    prompt_variant: str = "default"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResponse:
    """Output of a VLM provider."""

    payload: dict[str, Any]
    raw_text: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)


def extraction_json_schema() -> dict[str, Any]:
    """JSON Schema used to request structured output from VLMs.

    Kept intentionally lightweight (the IR builder enforces the full IR
    invariants) so VLMs don't trip on provenance/ID requirements.
    """
    point = {
        "type": "array",
        "items": {"type": "number"},
        "minItems": 2,
        "maxItems": 2,
    }
    bbox = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
            "w": {"type": "number"},
            "h": {"type": "number"},
        },
        "required": ["x", "y", "w", "h"],
        "additionalProperties": False,
    }
    quantity = {
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "unit": {"type": ["string", "null"]},
            "raw": {"type": ["string", "null"]},
        },
        "required": ["value"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "domain": {"type": ["string", "null"]},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string"},
                        "label": {"type": ["string", "null"]},
                        "anchor": point,
                        "bbox": {"anyOf": [bbox, {"type": "null"}]},
                        "domain": {"type": ["string", "null"]},
                        "confidence": {"type": "number"},
                        "properties": {"type": "object", "additionalProperties": True},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "ports": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": ["string", "null"]},
                                    "position": point,
                                    "direction": {
                                        "type": ["string", "null"],
                                        "enum": ["in", "out", "bidir", "neutral", None],
                                    },
                                },
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["id", "kind"],
                    "additionalProperties": False,
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "source_port": {"type": ["string", "null"]},
                        "target_port": {"type": ["string", "null"]},
                        "kind": {"type": "string"},
                        "label": {"type": ["string", "null"]},
                        "directed": {"type": "boolean"},
                        "polyline": {"type": "array", "items": point},
                        "domain": {"type": ["string", "null"]},
                        "confidence": {"type": "number"},
                        "properties": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["source", "target"],
                    "additionalProperties": False,
                },
            },
            "constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "targets": {"type": "array", "items": {"type": "string"}},
                        "expression": {"type": ["string", "null"]},
                        "value": {"anyOf": [quantity, {"type": "null"}]},
                    },
                    "required": ["kind", "targets"],
                    "additionalProperties": False,
                },
            },
            "equations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "raw": {"type": "string"},
                        "lhs": {"type": ["string", "null"]},
                        "rhs": {"type": ["string", "null"]},
                        "variables": {"type": "object", "additionalProperties": {"type": "string"}},
                    },
                    "required": ["raw"],
                    "additionalProperties": False,
                },
            },
            "datasets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": ["string", "null"]},
                        "axes": {"type": "array", "items": {"type": "string"}},
                        "series": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "values": {"type": "array", "items": {"type": "number"}},
                                },
                                "required": ["name", "values"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "parameters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "default": {"anyOf": [quantity, {"type": "null"}]},
                        "bounds": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        "description": {"type": ["string", "null"]},
                        "targets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["nodes", "edges"],
    }


class VLMProvider(abc.ABC):
    """Abstract base for multimodal extraction providers."""

    name: str = "abstract"

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        self.model = model
        self.kwargs = kwargs

    @abc.abstractmethod
    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        """Run extraction. Must return a payload conforming to ``extraction_json_schema``."""

    def healthcheck(self) -> bool:
        """Return True if the provider has credentials / model availability to run."""
        return True


def load_provider(name: str, **kwargs: Any) -> VLMProvider:
    """Instantiate a provider by registered name."""
    factory = provider_registry.get(name)
    return factory(**kwargs)
