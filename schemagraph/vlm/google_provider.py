"""Google Gemini multimodal VLM provider."""

from __future__ import annotations

import json
from typing import Any

from schemagraph.config import get_settings
from schemagraph.vlm.base import (
    ExtractionRequest,
    ExtractionResponse,
    VLMProvider,
    extraction_json_schema,
)
from schemagraph.vlm.prompts import primitives_hint_block, render_prompt


class GoogleProvider(VLMProvider):
    """Google Gemini provider.

    Supports two backends through the same ``google-genai`` SDK:

    * **AI Studio / Developer API** (default) — set ``GOOGLE_API_KEY``.
      Billed via AI Studio prepayment credits.
    * **Vertex AI** — set ``SCHEMAGRAPH_GOOGLE_USE_VERTEX=true``,
      ``SCHEMAGRAPH_GOOGLE_PROJECT=<gcp-project-id>``, and
      ``SCHEMAGRAPH_GOOGLE_LOCATION=us-central1`` (or another region).
      Authentication is via Application Default Credentials, set up once
      with ``gcloud auth application-default login``. Billed via Google
      Cloud — consumes the standard $300 free-trial credit.
    """

    name = "google"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        use_vertex: bool | None = None,
        project: str | None = None,
        location: str | None = None,
        **kwargs: Any,
    ) -> None:
        settings = get_settings()
        super().__init__(model=model or settings.google_model, **kwargs)
        self._api_key = api_key or settings.google_api_key
        self._use_vertex = (
            settings.google_use_vertex if use_vertex is None else use_vertex
        )
        self._project = project or settings.google_project
        self._location = location or settings.google_location

    def _client(self):
        try:
            from google import genai  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "The Google provider requires the 'google-genai' package. "
                "Install with: pip install 'schemagraph[google]'"
            ) from e

        if self._use_vertex:
            if not self._project:
                raise RuntimeError(
                    "Vertex AI mode requires SCHEMAGRAPH_GOOGLE_PROJECT to be set "
                    "(your GCP project id)."
                )
            return genai.Client(
                vertexai=True,
                project=self._project,
                location=self._location,
            )

        if not self._api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Either set GOOGLE_API_KEY for the "
                "AI Studio Developer API, or set SCHEMAGRAPH_GOOGLE_USE_VERTEX=true "
                "(plus SCHEMAGRAPH_GOOGLE_PROJECT) for Vertex AI."
            )
        return genai.Client(api_key=self._api_key)

    def healthcheck(self) -> bool:
        if self._use_vertex:
            return bool(self._project)
        return bool(self._api_key)

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        client = self._client()
        # Both Developer API and Vertex have schema quirks; clean for both,
        # since the AI Studio restrictions are a superset of Vertex's strictness.
        schema = _clean_for_gemini(extraction_json_schema())

        primitives_block = primitives_hint_block(request.primitives)
        width = request.primitives.width_px if request.primitives else 0
        height = request.primitives.height_px if request.primitives else 0
        system, user = render_prompt(
            request.prompt_variant,
            domain_hint=request.domain_hint,
            width=width,
            height=height,
            primitives_block=primitives_block,
        )

        from google.genai import types  # type: ignore

        contents = [
            types.Part.from_text(text=system + "\n\n" + user),
            types.Part.from_bytes(data=request.image_bytes, mime_type=request.mime),
        ]

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        raw = response.text or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"nodes": [], "edges": [], "_parse_error": raw}

        usage = {}
        if getattr(response, "usage_metadata", None) is not None:
            usage = {
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
            }

        return ExtractionResponse(
            payload=payload,
            raw_text=raw,
            model=self.model or "gemini",
            provider=self.name,
            usage=usage,
        )


_UNSUPPORTED_KEYS = {
    "additionalProperties",
    "additional_properties",
    "$schema",
    "$defs",
    "anyOf",
    "oneOf",
}


def _clean_for_gemini(schema):
    """Adapt our JSON Schema to Gemini Developer API's restricted subset.

    Gemini's schema validator rejects:
    - ``additionalProperties`` (only allowed on Vertex Enterprise),
    - ``anyOf`` / ``oneOf`` of complex object types,
    - array-valued ``type`` (e.g. ``["string", "null"]``).
    We strip the unsupported keys and collapse union ``type`` arrays to
    their first non-``null`` member, with ``nullable: true`` when the
    union included ``null``.
    """
    if isinstance(schema, dict):
        out = {}
        for k, v in schema.items():
            if k in _UNSUPPORTED_KEYS:
                continue
            if k == "type" and isinstance(v, list):
                non_null = [t for t in v if t != "null"]
                out["type"] = non_null[0] if non_null else "string"
                if "null" in v:
                    out["nullable"] = True
                continue
            if k == "enum" and isinstance(v, list):
                # Gemini rejects None entries in enums; drop them and mark nullable.
                cleaned = [x for x in v if x is not None]
                out["enum"] = cleaned
                if len(cleaned) != len(v):
                    out["nullable"] = True
                continue
            out[k] = _clean_for_gemini(v)
        return out
    if isinstance(schema, list):
        return [_clean_for_gemini(x) for x in schema]
    return schema
