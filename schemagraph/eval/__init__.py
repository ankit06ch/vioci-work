"""Golden-fixture evaluation harness for schemagraph."""

from schemagraph.eval.harness import (
    EvalReport,
    FixtureResult,
    Metrics,
    diff_diagrams,
    evaluate_dataset,
    evaluate_fixture,
)

__all__ = [
    "EvalReport",
    "FixtureResult",
    "Metrics",
    "diff_diagrams",
    "evaluate_dataset",
    "evaluate_fixture",
]
