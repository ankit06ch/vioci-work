"""Simulator ABC + plugin registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Mapping

from schemagraph.ir.schema import Dataset, Diagram
from schemagraph.physics.parametric import apply_parameters
from schemagraph.registry import _Registry


@dataclass
class SimulationResult:
    """Output of a Simulator run.

    ``datasets`` follow the same shape as :class:`schemagraph.ir.schema.Dataset`
    so they can be merged back into the source Diagram for downstream
    reasoning / visualization.
    """

    engine: str
    success: bool
    datasets: list[Dataset] = field(default_factory=list)
    log: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)  # filename -> path
    metadata: dict[str, Any] = field(default_factory=dict)


class Simulator(abc.ABC):
    """Abstract base for domain-specific simulation adapters."""

    name: str = "abstract"
    domain: str | None = None

    @abc.abstractmethod
    def run(
        self,
        diagram: Diagram,
        *,
        parameters: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> SimulationResult:
        """Execute the simulation for ``diagram`` with the given overrides."""

    def healthcheck(self) -> tuple[bool, str]:
        """Return (available, message). Default: assume available."""
        return True, ""

    # Convenience: apply parameter overrides up-front. Subclasses use this
    # to obtain the *effective* Diagram before generating their input file.
    def _resolve(self, diagram: Diagram, parameters: Mapping[str, Any] | None) -> Diagram:
        if not parameters:
            return diagram
        return apply_parameters(diagram, parameters)


simulator_registry = _Registry("schemagraph.simulators")


def load_simulator(name: str, **kwargs: Any) -> Simulator:
    factory = simulator_registry.get(name)
    return factory(**kwargs)


def list_simulators() -> list[str]:
    return simulator_registry.names()


def simulate(
    diagram: Diagram,
    *,
    engine: str,
    parameters: Mapping[str, Any] | None = None,
    **options: Any,
) -> SimulationResult:
    sim = load_simulator(engine)
    return sim.run(diagram, parameters=parameters, **options)
