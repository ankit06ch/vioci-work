"""Analytic RC-circuit simulator.

Runs a closed-form step-response simulation for first-order RC circuits
*without* requiring any external solver. Used both as a fast smoke
simulator and as a reference for validating the ngspice adapter wiring.

If the input Diagram doesn't look like a simple RC, returns
``success=False`` rather than guessing.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from schemagraph.ir import ids as _ids
from schemagraph.ir.schema import Dataset, DatasetSeries, Diagram, Provenance, Quantity
from schemagraph.physics.units import normalize_quantity
from schemagraph.simulate.base import SimulationResult, Simulator


class AnalyticRCSimulator(Simulator):
    name = "analytic_rc"
    domain = "electrical"

    def healthcheck(self) -> tuple[bool, str]:
        return True, "pure-python analytic"

    def run(
        self,
        diagram: Diagram,
        *,
        parameters: Mapping[str, Any] | None = None,
        t_end_s: float = 5e-3,
        n_samples: int = 200,
        v_in: float | None = None,
        **options: Any,
    ) -> SimulationResult:
        effective = self._resolve(diagram, parameters)

        r = _first_value(effective, "resistor", "ohm")
        c = _first_value(effective, "capacitor", "farad")
        v = v_in if v_in is not None else _first_value(effective, "voltage_source", "volt") or 1.0
        if r is None or c is None:
            return SimulationResult(
                engine=self.name,
                success=False,
                log=f"missing R={r} or C={c}; analytic_rc cannot simulate",
            )
        tau = r * c
        if tau <= 0 or not math.isfinite(tau):
            return SimulationResult(
                engine=self.name,
                success=False,
                log=f"non-physical tau={tau}",
            )
        ts = [t_end_s * i / (n_samples - 1) for i in range(n_samples)]
        vs = [v * (1.0 - math.exp(-t / tau)) for t in ts]

        ds = Dataset(
            id=_ids.dataset_id(effective.id, "analytic_rc_step", ["t", "v_out"]),
            name="analytic_rc_step",
            axes=["t (s)", "V (V)"],
            series=[
                DatasetSeries(name="t", values=ts),
                DatasetSeries(name="v_out", values=vs),
            ],
            provenance=Provenance(stage="annotator", producer="AnalyticRCSimulator"),
        )
        return SimulationResult(
            engine=self.name,
            success=True,
            datasets=[ds],
            metadata={"R": r, "C": c, "tau": tau, "V": v},
        )


def _first_value(diagram: Diagram, kind: str, target_unit: str) -> float | None:
    for n in diagram.nodes:
        if n.kind != kind:
            continue
        v = n.properties.get("value")
        if isinstance(v, Quantity):
            if v.unit:
                conv = normalize_quantity(v, target_unit)
                if conv is not None:
                    return float(conv.value)
            return float(v.value)
    return None
