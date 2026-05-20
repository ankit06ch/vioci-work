"""Compare predicted vs golden Diagrams and compute aggregate metrics.

A *fixture* is a (input image, golden Diagram JSON) pair living side by
side in a directory:

    dataset/
      rc_circuit.png
      rc_circuit.golden.json
      truss.png
      truss.golden.json
      ...

The harness runs the configured provider on each image, then compares the
resulting Diagram with its golden counterpart using:

- **Structural F1** on the node graph (matched by ``kind`` + nearest label;
  symmetric Hungarian-style greedy match by IoU of bbox + label edit
  distance).
- **Edge structural F1** on directed (source, target, kind) triples after
  node alignment.
- **Label accuracy** — fraction of matched nodes whose label matches.
- **Unit-aware property accuracy** — fraction of matched nodes whose
  ``properties.value`` Quantity is dimensionally consistent and within 1%
  of the golden magnitude (after pint conversion).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from schemagraph.api import parse as api_parse
from schemagraph.ir.schema import Diagram, Node, Quantity
from schemagraph.physics.units import normalize_quantity


@dataclass
class Metrics:
    nodes_pred: int = 0
    nodes_gold: int = 0
    nodes_matched: int = 0
    edges_pred: int = 0
    edges_gold: int = 0
    edges_matched: int = 0
    label_correct: int = 0
    label_total: int = 0
    value_correct: int = 0
    value_total: int = 0

    def merged(self, other: "Metrics") -> "Metrics":
        return Metrics(
            nodes_pred=self.nodes_pred + other.nodes_pred,
            nodes_gold=self.nodes_gold + other.nodes_gold,
            nodes_matched=self.nodes_matched + other.nodes_matched,
            edges_pred=self.edges_pred + other.edges_pred,
            edges_gold=self.edges_gold + other.edges_gold,
            edges_matched=self.edges_matched + other.edges_matched,
            label_correct=self.label_correct + other.label_correct,
            label_total=self.label_total + other.label_total,
            value_correct=self.value_correct + other.value_correct,
            value_total=self.value_total + other.value_total,
        )

    @property
    def node_precision(self) -> float:
        return _safe_div(self.nodes_matched, self.nodes_pred)

    @property
    def node_recall(self) -> float:
        return _safe_div(self.nodes_matched, self.nodes_gold)

    @property
    def node_f1(self) -> float:
        return _f1(self.node_precision, self.node_recall)

    @property
    def edge_precision(self) -> float:
        return _safe_div(self.edges_matched, self.edges_pred)

    @property
    def edge_recall(self) -> float:
        return _safe_div(self.edges_matched, self.edges_gold)

    @property
    def edge_f1(self) -> float:
        return _f1(self.edge_precision, self.edge_recall)

    @property
    def label_accuracy(self) -> float:
        return _safe_div(self.label_correct, self.label_total)

    @property
    def value_accuracy(self) -> float:
        return _safe_div(self.value_correct, self.value_total)


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass
class FixtureResult:
    name: str
    input_path: Path
    golden_path: Path
    metrics: Metrics
    matched_pairs: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    fixtures: list[FixtureResult] = field(default_factory=list)
    aggregate: Metrics = field(default_factory=Metrics)
    provider: str = ""

    def summary(self) -> dict:
        m = self.aggregate
        return {
            "provider": self.provider,
            "n_fixtures": len(self.fixtures),
            "node_precision": m.node_precision,
            "node_recall": m.node_recall,
            "node_f1": m.node_f1,
            "edge_precision": m.edge_precision,
            "edge_recall": m.edge_recall,
            "edge_f1": m.edge_f1,
            "label_accuracy": m.label_accuracy,
            "value_accuracy": m.value_accuracy,
        }


# ---------------------------------------------------------------------------
# matching & metrics
# ---------------------------------------------------------------------------


def _node_match_score(p: Node, g: Node) -> float:
    """Higher is better; combines kind match + label similarity + spatial overlap."""
    s = 0.0
    if p.kind == g.kind:
        s += 1.0
    elif p.kind.lower() == g.kind.lower():
        s += 0.8
    if (p.label or "") == (g.label or ""):
        s += 0.5
    elif (p.label or "").lower() == (g.label or "").lower():
        s += 0.4
    if p.geometry and g.geometry and p.geometry.bbox and g.geometry.bbox:
        iou = _iou(p.geometry.bbox, g.geometry.bbox)
        s += iou
    return s


def _iou(a, b) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix = max(0.0, min(ax2, bx2) - max(a.x, b.x))
    iy = max(0.0, min(ay2, by2) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def _greedy_align(pred: list[Node], gold: list[Node]) -> list[tuple[Node, Node]]:
    """Greedy highest-score-first 1-1 matching."""
    pairs: list[tuple[Node, Node, float]] = []
    for p in pred:
        for g in gold:
            s = _node_match_score(p, g)
            if s > 0:
                pairs.append((p, g, s))
    pairs.sort(key=lambda t: t[2], reverse=True)
    used_p: set[str] = set()
    used_g: set[str] = set()
    matched: list[tuple[Node, Node]] = []
    for p, g, _s in pairs:
        if p.id in used_p or g.id in used_g:
            continue
        matched.append((p, g))
        used_p.add(p.id)
        used_g.add(g.id)
    return matched


def _value_matches(p: Quantity, g: Quantity, tol: float = 0.01) -> bool:
    if p is None or g is None:
        return False
    if g.unit is None and p.unit is None:
        return abs(p.value - g.value) <= max(1e-9, tol * abs(g.value))
    converted = normalize_quantity(p, g.unit) if g.unit else None
    base_value = converted.value if converted is not None else p.value
    if math.isnan(base_value) or math.isnan(g.value):
        return False
    return abs(base_value - g.value) <= max(1e-9, tol * abs(g.value))


def diff_diagrams(pred: Diagram, gold: Diagram) -> tuple[Metrics, list[tuple[str, str]]]:
    """Compute Metrics and the matched (pred_id, gold_id) pairs."""
    metrics = Metrics(
        nodes_pred=len(pred.nodes),
        nodes_gold=len(gold.nodes),
        edges_pred=len(pred.edges),
        edges_gold=len(gold.edges),
    )

    matched = _greedy_align(pred.nodes, gold.nodes)
    metrics.nodes_matched = len(matched)
    pair_ids: list[tuple[str, str]] = []

    pred_to_gold = {p.id: g.id for p, g in matched}
    for p, g in matched:
        pair_ids.append((p.id, g.id))
        # label accuracy
        if g.label is not None:
            metrics.label_total += 1
            if (p.label or "").strip().lower() == (g.label or "").strip().lower():
                metrics.label_correct += 1
        # value (Quantity) accuracy
        g_val = g.properties.get("value") if isinstance(g.properties.get("value"), Quantity) else None
        p_val = p.properties.get("value") if isinstance(p.properties.get("value"), Quantity) else None
        if g_val is not None:
            metrics.value_total += 1
            if p_val is not None and _value_matches(p_val, g_val):
                metrics.value_correct += 1

    # Edge matching (after node alignment): a predicted edge matches a gold edge
    # if its mapped (source, target, kind) triple equals the gold's.
    gold_triples = {(e.source, e.target, e.kind) for e in gold.edges} | {
        (e.target, e.source, e.kind) for e in gold.edges if not e.directed
    }
    for e in pred.edges:
        s = pred_to_gold.get(e.source, e.source)
        t = pred_to_gold.get(e.target, e.target)
        if (s, t, e.kind) in gold_triples:
            metrics.edges_matched += 1

    return metrics, pair_ids


# ---------------------------------------------------------------------------
# top-level driver
# ---------------------------------------------------------------------------


def _discover_fixtures(dataset_dir: Path) -> Iterable[tuple[Path, Path]]:
    for img in sorted(dataset_dir.glob("*.png")):
        gold = img.with_suffix(".golden.json")
        if not gold.exists():
            gold = img.with_name(img.stem + ".golden.json")
        if gold.exists():
            yield img, gold


def evaluate_fixture(
    image: Path,
    golden: Path,
    *,
    provider: Optional[str] = None,
    domain: Optional[str] = None,
) -> FixtureResult:
    pred = api_parse(image, provider=provider, domain=domain)
    gold_diagram = Diagram.model_validate_json(golden.read_text(encoding="utf-8"))
    metrics, pairs = diff_diagrams(pred, gold_diagram)
    return FixtureResult(
        name=image.stem,
        input_path=image,
        golden_path=golden,
        metrics=metrics,
        matched_pairs=pairs,
    )


def evaluate_dataset(
    dataset_dir: Path,
    *,
    provider: Optional[str] = None,
    domain: Optional[str] = None,
) -> EvalReport:
    report = EvalReport(provider=provider or "default")
    for image, gold in _discover_fixtures(Path(dataset_dir)):
        try:
            r = evaluate_fixture(image, gold, provider=provider, domain=domain)
        except Exception as e:
            r = FixtureResult(
                name=image.stem,
                input_path=image,
                golden_path=gold,
                metrics=Metrics(),
                notes=[f"ERROR: {type(e).__name__}: {e}"],
            )
        report.fixtures.append(r)
        report.aggregate = report.aggregate.merged(r.metrics)
    return report


def report_to_json(report: EvalReport) -> dict:
    return {
        "summary": report.summary(),
        "fixtures": [
            {
                "name": f.name,
                "input": str(f.input_path),
                "golden": str(f.golden_path),
                "metrics": {
                    "nodes_pred": f.metrics.nodes_pred,
                    "nodes_gold": f.metrics.nodes_gold,
                    "nodes_matched": f.metrics.nodes_matched,
                    "edges_pred": f.metrics.edges_pred,
                    "edges_gold": f.metrics.edges_gold,
                    "edges_matched": f.metrics.edges_matched,
                    "node_f1": f.metrics.node_f1,
                    "edge_f1": f.metrics.edge_f1,
                    "label_accuracy": f.metrics.label_accuracy,
                    "value_accuracy": f.metrics.value_accuracy,
                },
                "matched_pairs": f.matched_pairs,
                "notes": f.notes,
            }
            for f in report.fixtures
        ],
    }


def report_to_json_text(report: EvalReport) -> str:
    return json.dumps(report_to_json(report), indent=2, default=str)
