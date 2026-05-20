"""Abstract exporter contract + plugin loader."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Union

from schemagraph.ir.schema import Diagram
from schemagraph.registry import exporter_registry


class Exporter(abc.ABC):
    """Abstract base for exporting a Diagram to a downstream format."""

    name: str = "abstract"
    default_extension: str = ""
    binary: bool = False

    @abc.abstractmethod
    def export(self, diagram: Diagram, **options: Any) -> Union[str, bytes, dict, Any]:
        """Return an in-memory representation of the export.

        Subclasses may also implement :meth:`write` for direct-to-disk efficiency.
        """

    def write(self, diagram: Diagram, path: Union[str, Path], **options: Any) -> Path:
        path = Path(path)
        data = self.export(diagram, **options)
        if isinstance(data, bytes):
            path.write_bytes(data)
        elif isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            # fallback: json
            import json

            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return path


def load_exporter(name: str, **kwargs: Any) -> Exporter:
    factory = exporter_registry.get(name)
    return factory(**kwargs)
