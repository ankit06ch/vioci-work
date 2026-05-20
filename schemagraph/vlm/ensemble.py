"""Ensemble / fallback VLM provider.

Wraps a list of providers and either:
- **fallback** mode: tries each provider in order, returning the first
  successful payload (default).
- **ensemble** mode: queries every provider and votes/merges results node
  by node, picking the highest-confidence payload per node id (cheap; a
  more sophisticated graph alignment can be added later).
"""

from __future__ import annotations

from typing import Any, Sequence

from schemagraph.vlm.base import (
    ExtractionRequest,
    ExtractionResponse,
    VLMProvider,
    load_provider,
)


class EnsembleProvider(VLMProvider):
    name = "ensemble"

    def __init__(
        self,
        providers: Sequence[VLMProvider | str] = (),
        mode: str = "fallback",
        provider_kwargs: dict | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model="ensemble", **kwargs)
        self.mode = mode
        pk = provider_kwargs or {}
        self._providers: list[VLMProvider] = []
        for p in providers:
            if isinstance(p, str):
                self._providers.append(load_provider(p, **pk.get(p, {})))
            else:
                self._providers.append(p)

    def healthcheck(self) -> bool:
        return any(p.healthcheck() for p in self._providers)

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        if not self._providers:
            raise RuntimeError("ensemble has no providers")
        if self.mode == "fallback":
            return self._fallback(request)
        if self.mode == "ensemble":
            return self._merge(request)
        raise ValueError(f"unknown ensemble mode: {self.mode!r}")

    # ------------------------------------------------------------------
    def _fallback(self, request: ExtractionRequest) -> ExtractionResponse:
        last_exc: Exception | None = None
        for p in self._providers:
            try:
                return p.extract(request)
            except Exception as e:
                last_exc = e
        raise RuntimeError(f"all ensemble providers failed: {last_exc!r}")

    def _merge(self, request: ExtractionRequest) -> ExtractionResponse:
        responses: list[ExtractionResponse] = []
        for p in self._providers:
            try:
                responses.append(p.extract(request))
            except Exception:
                continue
        if not responses:
            raise RuntimeError("no providers returned a usable response")

        # node-wise highest-confidence merge by local id
        merged_nodes: dict[str, dict] = {}
        merged_edges: dict[tuple[str, str], dict] = {}
        constraints: list = []
        equations: list = []
        datasets: list = []
        parameters: list = []
        for r in responses:
            for n in r.payload.get("nodes", []) or []:
                key = str(n.get("id"))
                if not key:
                    continue
                existing = merged_nodes.get(key)
                if existing is None or float(n.get("confidence", 0.0)) > float(
                    existing.get("confidence", 0.0)
                ):
                    merged_nodes[key] = n
            for e in r.payload.get("edges", []) or []:
                key = (str(e.get("source")), str(e.get("target")))
                existing = merged_edges.get(key)
                if existing is None or float(e.get("confidence", 0.0)) > float(
                    existing.get("confidence", 0.0)
                ):
                    merged_edges[key] = e
            constraints.extend(r.payload.get("constraints", []) or [])
            equations.extend(r.payload.get("equations", []) or [])
            datasets.extend(r.payload.get("datasets", []) or [])
            parameters.extend(r.payload.get("parameters", []) or [])

        merged_payload = {
            "domain": next((r.payload.get("domain") for r in responses if r.payload.get("domain")), None),
            "nodes": list(merged_nodes.values()),
            "edges": list(merged_edges.values()),
            "constraints": constraints,
            "equations": equations,
            "datasets": datasets,
            "parameters": parameters,
        }
        return ExtractionResponse(
            payload=merged_payload,
            raw_text="<merged>",
            model="+".join(r.model for r in responses),
            provider=self.name,
            usage={"providers": len(responses)},
        )
