"""OpenAI multimodal VLM provider.

Uses Responses-style structured-output JSON (json_schema response format)
on a model that supports images (e.g. ``gpt-4o``, ``gpt-4o-mini``,
``gpt-4.1``). The model name is configurable; the default comes from
``SCHEMAGRAPH_OPENAI_MODEL`` / ``Settings.openai_model``.
"""

from __future__ import annotations

import base64
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


class OpenAIProvider(VLMProvider):
    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        settings = get_settings()
        super().__init__(model=model or settings.openai_model, **kwargs)
        self._api_key = api_key or settings.openai_api_key
        self._base_url = base_url or settings.openai_base_url

    def _client(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "The OpenAI provider requires the 'openai' package. "
                "Install with: pip install 'schemagraph[openai]'"
            ) from e
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set SCHEMAGRAPH_OPENAI_API_KEY "
                "or OPENAI_API_KEY in the environment."
            )
        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return OpenAI(**kwargs)

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

        b64 = base64.b64encode(request.image_bytes).decode("ascii")
        image_url = f"data:{request.mime};base64,{b64}"

        completion = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "schemagraph_extraction",
                    "schema": schema,
                    "strict": False,
                },
            },
            temperature=0.0,
        )

        raw = completion.choices[0].message.content or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"nodes": [], "edges": [], "_parse_error": raw}

        usage = {}
        if getattr(completion, "usage", None) is not None:
            usage = {
                "input_tokens": completion.usage.prompt_tokens,
                "output_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }

        return ExtractionResponse(
            payload=payload,
            raw_text=raw,
            model=self.model or "openai",
            provider=self.name,
            usage=usage,
        )
