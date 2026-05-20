"""FEniCS-friendly export.

Emits a Python skeleton that defines a `dolfinx` problem set-up with the
extracted geometry and constraints baked in. The user is expected to
fill in the variational form (this exporter does *not* attempt to derive
PDEs from a sketch); it provides the boilerplate so a user can go from a
hand-drawn schematic to a ready-to-run FEniCS script in seconds.
"""

from __future__ import annotations

from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram


class FEniCSExporter(Exporter):
    name = "fenics"
    default_extension = "py"
    binary = False

    def export(self, diagram: Diagram, *, mesh_resolution: int = 32, **options: Any) -> str:
        nodes_doc = "\n".join(
            f"    # node {n.id}: kind={n.kind!r} label={n.label!r} domain={n.domain!r}"
            for n in diagram.nodes
        )
        constraints_doc = "\n".join(
            f"    # constraint {c.kind} on {c.targets}: {c.expression}"
            for c in diagram.constraints
        )
        equations_doc = "\n".join(
            f"    # equation {eq.raw}  ->  sympy: {eq.sympy_repr}"
            for eq in diagram.equations
        )
        parameters_doc = "\n".join(
            f"    {p.name}: float = {p.default.value if p.default else 1.0!r}  # {p.default.unit if p.default else 'dimensionless'}"
            for p in diagram.parameters
        )

        return f'''\
"""Auto-generated FEniCS skeleton from schemagraph diagram {diagram.id}.

Fill in the variational form and run with `python {diagram.id}.py`.
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np

try:
    import dolfinx
    from dolfinx import fem, mesh
    from mpi4py import MPI
except ImportError as e:
    raise SystemExit(
        "FEniCS (dolfinx) is not installed. See https://fenicsproject.org for setup."
    ) from e


@dataclass
class Params:
{parameters_doc or "    pass"}


def build_problem(params: Params):
    # Auto-extracted topology:
{nodes_doc or "    # (no nodes extracted)"}

    # Auto-extracted constraints (apply via fem.dirichletbc()):
{constraints_doc or "    # (no constraints extracted)"}

    # Auto-extracted equations (use to set up the variational form):
{equations_doc or "    # (no equations extracted)"}

    # Default mesh: unit square at resolution {mesh_resolution}
    domain = mesh.create_unit_square(MPI.COMM_WORLD, {mesh_resolution}, {mesh_resolution})
    V = fem.functionspace(domain, ("Lagrange", 1))

    # TODO: define trial/test functions and the variational form here.
    # u = fem.Function(V)
    # ...
    return domain, V


if __name__ == "__main__":
    params = Params()
    domain, V = build_problem(params)
    print(f"FEniCS skeleton ready: {{V.dofmap.index_map.size_global}} DoF")
'''
