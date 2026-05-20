"""schemagraph.simulate: uniform Simulator interface over domain solvers.

A :class:`Simulator` adapter wraps an external solver (ngspice, FEniCS,
OpenFOAM, ...) behind a single ``run(diagram, parameters, **options)``
contract. Adapters are registered in a plugin registry so callers can do:

    from schemagraph import simulate
    result = simulate(diagram, engine="ngspice", parameters={"R": "22k"})

The intent is that the same parsed Diagram can be both *exported* to a
domain format and *executed* via the matching simulator, under arbitrary
user-defined parameter overrides.
"""

from schemagraph.simulate.analytic_rc import AnalyticRCSimulator
from schemagraph.simulate.base import (
    SimulationResult,
    Simulator,
    list_simulators,
    load_simulator,
    simulate,
    simulator_registry,
)
from schemagraph.simulate.fenics_sim import FEniCSSimulator
from schemagraph.simulate.ngspice_sim import NgSpiceSimulator
from schemagraph.simulate.openfoam_sim import OpenFOAMSimulator

simulator_registry.register("analytic_rc", AnalyticRCSimulator)
simulator_registry.register("ngspice", NgSpiceSimulator)
simulator_registry.register("fenics", FEniCSSimulator)
simulator_registry.register("openfoam", OpenFOAMSimulator)

__all__ = [
    "Simulator",
    "SimulationResult",
    "list_simulators",
    "load_simulator",
    "simulate",
    "AnalyticRCSimulator",
    "NgSpiceSimulator",
    "FEniCSSimulator",
    "OpenFOAMSimulator",
]
