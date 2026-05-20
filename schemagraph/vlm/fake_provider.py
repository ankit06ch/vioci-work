"""A deterministic fake VLM provider for tests and offline use.

The provider returns a payload supplied at construction time (or via
``inject_payload``). Useful in CI and for golden-fixture evaluation
without spending real API tokens.
"""

from __future__ import annotations

import json
from typing import Any

from schemagraph.vlm.base import ExtractionRequest, ExtractionResponse, VLMProvider


class FakeProvider(VLMProvider):
    name = "fake"

    def __init__(self, payload: dict | None = None, model: str = "fake-1", **kwargs: Any) -> None:
        super().__init__(model=model, **kwargs)
        self._payload = payload or {"nodes": [], "edges": []}

    def inject_payload(self, payload: dict) -> None:
        self._payload = payload

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        return ExtractionResponse(
            payload=dict(self._payload),
            raw_text=json.dumps(self._payload),
            model=self.model or "fake-1",
            provider=self.name,
        )

    def healthcheck(self) -> bool:
        return True
