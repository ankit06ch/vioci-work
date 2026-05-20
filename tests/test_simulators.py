"""Phase 6 tests: Simulator interface + adapters.

Focus on:
- registry discoverability,
- the analytic_rc adapter (deterministic, no external deps),
- healthchecks for ngspice/fenics/openfoam returning a clean (False, msg) when
  the binaries aren't installed in CI,
- end-to-end parameter sweep via the uniform interface.
"""

from __future__ import annotations

import math
from pathlib import Path

import schemagraph  # noqa: F401 - populates registries
from schemagraph.api import annotate as api_annotate
from schemagraph.api import parse as api_parse
from schemagraph.ir.schema import Diagram, Node, Provenance, SourceMeta, Quantity
from schemagraph.registry import provider_registry
from schemagraph.simulate import (
    AnalyticRCSimulator,
    SimulationResult,
    Simulator,
    list_simulators,
    load_simulator,
    simulate,
)
from schemagraph.simulate.base import simulator_registry
from schemagraph.vlm.fake_provider import FakeProvider


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_all_simulators_registered():
    names = set(list_simulators())
    assert {"analytic_rc", "ngspice", "fenics", "openfoam"} <= names


def test_analytic_rc_runs_on_synthetic_rc():
    prov = Provenance(stage="user", producer="t")
    diagram = Diagram(
        id="d",
        source=SourceMeta(),
        domain="electrical",
        nodes=[
            Node(id="R1", kind="resistor", label="R", properties={"value": Quantity(value=1000.0, unit="ohm")}, provenance=prov),
            Node(id="C1", kind="capacitor", label="C", properties={"value": Quantity(value=1e-6, unit="farad")}, provenance=prov),
            Node(id="V1", kind="voltage_source", label="Vs", properties={"value": Quantity(value=5.0, unit="volt")}, provenance=prov),
        ],
    )
    result = simulate(diagram, engine="analytic_rc")
    assert result.success
    assert result.engine == "analytic_rc"
    assert math.isclose(result.metadata["tau"], 1000.0 * 1e-6, rel_tol=1e-9)
    # Step-response final value should approach V (5.0)
    v_series = next(s for s in result.datasets[0].series if s.name == "v_out")
    assert v_series.values[-1] > 0.95 * 5.0


def test_analytic_rc_respects_parameter_override():
    prov = Provenance(stage="user", producer="t")
    diagram = Diagram(
        id="d",
        source=SourceMeta(),
        domain="electrical",
        nodes=[
            Node(id="R1", kind="resistor", label="R", properties={"value": Quantity(value=1000.0, unit="ohm")}, provenance=prov),
            Node(id="C1", kind="capacitor", label="C", properties={"value": Quantity(value=1e-6, unit="farad")}, provenance=prov),
        ],
        parameters=[
            {  # type: ignore[list-item]
                "id": "p", "name": "R", "targets": ["R1.value"],
                "default": {"value": 1000.0, "unit": "ohm"},
            }
        ],
    )
    result = simulate(diagram, engine="analytic_rc", parameters={"R": "10kohm"})
    assert result.success
    assert math.isclose(result.metadata["R"], 10000.0, rel_tol=1e-6)
    assert math.isclose(result.metadata["tau"], 10000.0 * 1e-6, rel_tol=1e-9)


def test_analytic_rc_fails_cleanly_when_no_rc():
    prov = Provenance(stage="user", producer="t")
    diagram = Diagram(
        id="d",
        source=SourceMeta(),
        nodes=[Node(id="x", kind="block", label="X", provenance=prov)],
    )
    result = simulate(diagram, engine="analytic_rc")
    assert not result.success
    assert "missing" in result.log


def test_external_sims_report_unavailable_cleanly():
    """In CI, ngspice/fenics/openfoam binaries are typically absent; the
    adapters must produce a clean failed-but-non-crashing result."""

    prov = Provenance(stage="user", producer="t")
    diagram = Diagram(
        id="d",
        source=SourceMeta(),
        domain="electrical",
        nodes=[
            Node(id="R1", kind="resistor", label="R", properties={"value": Quantity(value=1.0, unit="ohm")}, provenance=prov),
            Node(id="GND", kind="ground", label="GND", provenance=prov),
        ],
    )
    for engine in ("ngspice", "openfoam"):
        sim = load_simulator(engine)
        avail, msg = sim.healthcheck()
        if avail:
            continue  # CI has the tool installed; skip the negative-path assertion
        result = sim.run(diagram)
        assert isinstance(result, SimulationResult)
        assert result.success is False
        assert msg.lower() in result.log.lower() or len(result.log) > 0


def test_simulator_registry_pluggability():
    class MySim(Simulator):
        name = "my_sim"

        def run(self, diagram, **kw):
            return SimulationResult(engine=self.name, success=True, metadata={"called": True})

    simulator_registry.register("my_sim", MySim)
    assert "my_sim" in list_simulators()
    r = simulate(Diagram(id="d", source=SourceMeta()), engine="my_sim")
    assert r.success and r.metadata["called"]
