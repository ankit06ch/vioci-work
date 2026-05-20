"""Anthropic Claude multimodal VLM provider."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from schemagraph.config import get_settings
from schemagraph.vlm.base import (
    ExtractionRequest,
    ExtractionResponse,
    VLMProvider,
    extraction_json_schema,
)
from schemagraph.vlm.prompts import primitives_hint_block, render_prompt


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class AnthropicProvider(VLMProvider):
    name = "anthropic"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        settings = get_settings()
        super().__init__(model=model or settings.anthropic_model, **kwargs)
        self._api_key = api_key or settings.anthropic_api_key

    def _client(self):
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "The Anthropic provider requires the 'anthropic' package. "
                "Install with: pip install 'schemagraph[anthropic]'"
            ) from e
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set SCHEMAGRAPH_ANTHROPIC_API_KEY "
                "or ANTHROPIC_API_KEY in the environment."
            )
        return Anthropic(api_key=self._api_key)

    def healthcheck(self) -> bool:
        return bool(self._api_key)

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        client = self._client()
        schema = extraction_json_schema()

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

        # Anthropic doesn't support strict json_schema response format yet
        # in the public API, so we inline the schema and ask for JSON-only.
        user_text = (
            user
            + "\n\nReturn ONLY a single JSON object matching this JSON Schema:\n"
            + json.dumps(schema)
        )

        b64 = base64.b64encode(request.image_bytes).decode("ascii")

        response = client.messages.create(
            model=self.model,
            max_tokens=8192,
            temperature=0.0,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": request.mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )

        raw = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        payload = _extract_json(raw)

        usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
        }

        return ExtractionResponse(
            payload=payload,
            raw_text=raw,
            model=self.model or "anthropic",
            provider=self.name,
            usage=usage,
        )


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try to extract the first balanced JSON object.
        depth = 0
        start = None
        for i, ch in enumerate(candidate):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(candidate[start : i + 1])
                    except json.JSONDecodeError:
                        continue
        return {"nodes": [], "edges": [], "_parse_error": text}
