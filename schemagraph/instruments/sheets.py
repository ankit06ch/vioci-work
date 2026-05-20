"""Per-instrument data sheets backed by JSONL files.

A "sheet" is one append-only ``.jsonl`` file per node-instance, stored
under ``<store_root>/sheets/<sheet_id>.jsonl``. Each line is one row.

We keep the store stdlib-only (no pandas) so install size stays light.
For richer querying, callers can read the JSONL directly with
``pandas.read_json(lines=True)`` or ``polars.read_ndjson``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


def sheet_id_for(instrument_id: str, node_id: str) -> str:
    """Deterministic, filesystem-safe sheet id."""
    h = hashlib.sha256()
    h.update(instrument_id.encode())
    h.update(b"|")
    h.update(node_id.encode())
    return f"{instrument_id}.{h.hexdigest()[:10]}"


class SheetMissingError(LookupError):
    """Raised when a sheet hasn't been attached yet."""


@dataclass
class SheetSummary:
    sheet_id: str
    rows: int
    fields: list[str]
    head: list[dict] = field(default_factory=list)
    stats: dict[str, dict] = field(default_factory=dict)


class SheetStore:
    """JSONL-backed per-instrument data store rooted at a single directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.dir = self.root / "sheets"

    # ----- IO -------------------------------------------------------
    def _path(self, sheet_id: str) -> Path:
        return self.dir / f"{sheet_id}.jsonl"

    def exists(self, sheet_id: str) -> bool:
        return self._path(sheet_id).exists()

    def list_sheets(self) -> list[str]:
        if not self.dir.exists():
            return []
        return sorted(p.stem for p in self.dir.glob("*.jsonl"))

    def attach_csv(self, sheet_id: str, csv_path: Path | str) -> int:
        """Convert a CSV (with header row) into JSONL under ``sheet_id``.

        Returns the number of rows written. Replaces any prior sheet.
        """
        csv_path = Path(csv_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        out = self._path(sheet_id)
        with csv_path.open("r", encoding="utf-8", newline="") as fh_in, out.open(
            "w", encoding="utf-8"
        ) as fh_out:
            reader = csv.DictReader(fh_in)
            n = 0
            for row in reader:
                fh_out.write(json.dumps(_coerce_row(row), separators=(",", ":")) + "\n")
                n += 1
        return n

    def append_rows(self, sheet_id: str, rows: Iterable[dict]) -> int:
        self.dir.mkdir(parents=True, exist_ok=True)
        out = self._path(sheet_id)
        n = 0
        with out.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(_coerce_row(r), separators=(",", ":")) + "\n")
                n += 1
        return n

    def _iter_rows(self, sheet_id: str) -> Iterable[dict]:
        path = self._path(sheet_id)
        if not path.exists():
            raise SheetMissingError(sheet_id)
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    # ----- queries --------------------------------------------------
    def count(self, sheet_id: str) -> int:
        if not self.exists(sheet_id):
            return 0
        n = 0
        for _ in self._iter_rows(sheet_id):
            n += 1
        return n

    def head(self, sheet_id: str, limit: int = 5) -> list[dict]:
        out: list[dict] = []
        for row in self._iter_rows(sheet_id):
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def query(
        self,
        sheet_id: str,
        *,
        where: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Filter rows by a simple Python boolean expression.

        Each row is exposed as a dict named ``r`` to the expression
        (``where="r['B3'] > 100 and r['lat'] < 45"``). We refuse to eval
        any expression containing imports or dunders, but this is *not* a
        sandbox — only run user-supplied queries you trust.
        """
        if where:
            self._validate_expr(where)
            compiled = compile(where, "<sheet-query>", "eval")
        else:
            compiled = None
        out: list[dict] = []
        for r in self._iter_rows(sheet_id):
            if compiled is None or bool(eval(compiled, {"__builtins__": {}}, {"r": r})):
                out.append(r)
                if len(out) >= limit:
                    break
        return out

    def summary(self, sheet_id: str, *, head_n: int = 3) -> SheetSummary:
        rows: list[dict] = []
        try:
            for r in self._iter_rows(sheet_id):
                rows.append(r)
        except SheetMissingError:
            return SheetSummary(sheet_id=sheet_id, rows=0, fields=[])

        fields: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)

        stats: dict[str, dict] = {}
        for f in fields:
            values = [r.get(f) for r in rows]
            numeric = [v for v in values if isinstance(v, (int, float)) and not _isnan(v)]
            if numeric:
                stats[f] = {
                    "count": len(numeric),
                    "min": min(numeric),
                    "max": max(numeric),
                    "mean": sum(numeric) / len(numeric),
                }
            else:
                non_null = [v for v in values if v not in (None, "")]
                stats[f] = {"count": len(non_null), "dtype": "string"}

        return SheetSummary(
            sheet_id=sheet_id,
            rows=len(rows),
            fields=fields,
            head=rows[:head_n],
            stats=stats,
        )

    # ----- helpers --------------------------------------------------
    @staticmethod
    def _validate_expr(expr: str) -> None:
        banned = ("__", "import ", "open(", "exec(", "eval(", "subprocess", "os.")
        for b in banned:
            if b in expr:
                raise ValueError(f"unsafe expression: contains {b!r}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _coerce_row(row: dict) -> dict:
    """Coerce raw CSV string values to float/int when possible."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
            continue
        if isinstance(v, (int, float, bool)):
            out[k] = v
            continue
        s = str(v).strip()
        if s == "":
            out[k] = None
            continue
        # try int
        try:
            iv = int(s)
            if str(iv) == s:
                out[k] = iv
                continue
        except ValueError:
            pass
        # try float
        try:
            out[k] = float(s)
            continue
        except ValueError:
            pass
        out[k] = s
    return out


def _isnan(x: float) -> bool:
    try:
        return math.isnan(x)
    except TypeError:
        return False


def open_buffer(text: str) -> io.StringIO:
    """Tiny helper used in tests to feed a CSV directly without writing to disk."""
    return io.StringIO(text)
