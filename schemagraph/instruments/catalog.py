"""Load and query the spacecraft instrument catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml


HERE = Path(__file__).parent


def catalog_path() -> Path:
    return HERE / "catalog.yaml"


@dataclass
class InstrumentEntry:
    """One instrument's schema."""

    id: str
    display_name: str
    aliases: list[str]
    data_product: str
    telemetry_fields: list[dict]
    extras: dict = field(default_factory=dict)

    def field_names(self) -> list[str]:
        return [f["name"] for f in self.telemetry_fields]

    def field_units(self) -> dict[str, str]:
        return {f["name"]: f.get("unit", "") for f in self.telemetry_fields}

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "data_product": self.data_product,
            "fields": self.field_names(),
            "units": self.field_units(),
            **self.extras,
        }


@dataclass
class Catalog:
    entries: dict[str, InstrumentEntry]

    def __iter__(self):
        return iter(self.entries.values())

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, instrument_id: str) -> Optional[InstrumentEntry]:
        return self.entries.get(instrument_id)

    def match(self, query: str) -> Optional[InstrumentEntry]:
        """Find an InstrumentEntry whose id, display name, or alias best
        matches ``query``. Case-insensitive substring + token match."""
        if not query:
            return None
        q = query.lower().strip()
        # Strict id / display name / alias match first.
        for e in self.entries.values():
            candidates = {e.id, e.display_name, *e.aliases}
            for c in candidates:
                if c.lower() == q:
                    return e
        # Substring / token-overlap fallback.
        best: tuple[float, InstrumentEntry | None] = (0.0, None)
        for e in self.entries.values():
            score = _score(q, [e.id, e.display_name, *e.aliases])
            if score > best[0]:
                best = (score, e)
        if best[1] is not None and best[0] >= 0.5:
            return best[1]
        return None


def _score(query: str, candidates: list[str]) -> float:
    q_tokens = set(_tokenize(query))
    best = 0.0
    for c in candidates:
        cl = c.lower()
        c_tokens = set(_tokenize(c))
        if not c_tokens or not q_tokens:
            continue
        overlap = len(q_tokens & c_tokens)
        union = len(q_tokens | c_tokens)
        jacc = overlap / union if union else 0.0
        # Substring bonus, but only for candidates that look like a real phrase
        # (>= 4 chars) — short aliases like "ST"/"TM" otherwise match inside
        # unrelated words like "thru-st-er".
        if len(cl) >= 4 and (query in cl or cl in query):
            jacc = max(jacc, 0.6)
        if jacc > best:
            best = jacc
    return best


def _tokenize(s: str) -> list[str]:
    import re

    return [t for t in re.split(r"[\s\-_/()\[\]]+", s.lower()) if t]


def load_catalog(path: Optional[Path] = None) -> Catalog:
    p = path or catalog_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    entries: dict[str, InstrumentEntry] = {}
    for key, body in raw.items():
        body = dict(body or {})
        entries[key] = InstrumentEntry(
            id=key,
            display_name=body.pop("display_name", key.replace("_", " ").title()),
            aliases=list(body.pop("aliases", []) or []),
            data_product=str(body.pop("data_product", "unknown")),
            telemetry_fields=list(body.pop("telemetry_fields", []) or []),
            extras=body,
        )
    return Catalog(entries=entries)


@lru_cache(maxsize=1)
def default_catalog() -> Catalog:
    return load_catalog()
