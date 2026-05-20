"""Parse uploaded SRS, PSD, and quasi-static load files."""

from __future__ import annotations

import csv
import io
import json
import math
from typing import Any


def parse_load_file(kind: str, content: str | bytes, filename: str = "") -> dict[str, Any]:
    kind = kind.lower()
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content

    if filename.endswith(".json") or text.strip().startswith("{"):
        data = json.loads(text)
        return {"kind": kind, "source": "upload", "data": data}

    rows = list(csv.DictReader(io.StringIO(text)))
    if kind == "psd":
        points = []
        for r in rows:
            f = float(r.get("freq_hz") or r.get("frequency") or r.get("f") or 0)
            a = float(r.get("asd_g2_hz") or r.get("asd") or r.get("amplitude") or 0)
            points.append({"freq_hz": f, "asd_g2_hz": a})
        return {"kind": "psd", "source": "upload", "points": points}
    if kind == "srs":
        points = []
        for r in rows:
            f = float(r.get("freq_hz") or r.get("frequency") or 0)
            pv = float(r.get("pv_in_s") or r.get("pv") or 0)
            points.append({"freq_hz": f, "pv_in_s": pv})
        return {"kind": "srs", "source": "upload", "points": points}
    if kind == "quasi_static":
        return {"kind": "quasi_static", "source": "upload", "rows": rows}
    return {"kind": kind, "source": "upload", "raw": rows}


def merge_psd(bundled: list[dict], override: dict | None) -> tuple[list[dict], str]:
    if override and override.get("points"):
        return override["points"], "upload"
    return bundled, "bundled"


def merge_srs(bundled: list[dict], override: dict | None) -> tuple[list[dict], str]:
    if override and override.get("points"):
        return override["points"], "upload"
    return bundled, "bundled"


def psd_grms(points: list[dict]) -> float:
    """Trapezoidal integration of ASD to GRMS."""
    if len(points) < 2:
        return 0.0
    pts = sorted(points, key=lambda p: p["freq_hz"])
    total = 0.0
    for i in range(len(pts) - 1):
        f1, f2 = pts[i]["freq_hz"], pts[i + 1]["freq_hz"]
        a1, a2 = pts[i].get("asd_g2_hz", 0), pts[i + 1].get("asd_g2_hz", 0)
        if f2 <= f1:
            continue
        total += 0.5 * (a1 + a2) * (f2 - f1)
    return math.sqrt(max(total, 0.0))
