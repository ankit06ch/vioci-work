"""Plugin registry for exporters, VLM providers, and physics annotators.

Plugins are discovered via Python entry points so third-party packages can
contribute domain-specific exporters (SPICE, URDF, FEniCS, OpenFOAM,
Modelica, orbital toolchains) and additional VLM providers without
modifying the core package.

Built-in plugins are always available; entry-point-discovered plugins
override or augment them by name.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class _Registry:
    """Generic name -> factory registry with lazy entry-point discovery."""

    def __init__(self, group: str) -> None:
        self._group = group
        self._builtins: dict[str, Callable[..., Any]] = {}
        self._eps: dict[str, EntryPoint] | None = None

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        self._builtins[name] = factory

    def _discover(self) -> dict[str, EntryPoint]:
        if self._eps is None:
            self._eps = {}
            try:
                eps = entry_points(group=self._group)
            except TypeError:  # pragma: no cover - older Python fallback
                eps = entry_points().get(self._group, [])  # type: ignore[attr-defined]
            for ep in eps:
                self._eps[ep.name] = ep
        return self._eps

    def names(self) -> list[str]:
        return sorted(set(self._builtins) | set(self._discover()))

    def get(self, name: str) -> Callable[..., Any]:
        eps = self._discover()
        if name in eps:
            return eps[name].load()
        if name in self._builtins:
            return self._builtins[name]
        raise KeyError(
            f"no plugin named {name!r} registered for group {self._group!r}; "
            f"available: {self.names()}"
        )


exporter_registry = _Registry("schemagraph.exporters")
provider_registry = _Registry("schemagraph.providers")
annotator_registry = _Registry("schemagraph.annotators")


def list_plugins() -> dict[str, list[str]]:
    return {
        "exporters": exporter_registry.names(),
        "providers": provider_registry.names(),
        "annotators": annotator_registry.names(),
    }
