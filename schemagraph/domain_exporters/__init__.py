"""Domain-specific exporters.

These are normally shipped as separate distributions (``schemagraph-spice``,
``schemagraph-urdf``, etc.) but are bundled here in v1 for convenience.
Each exporter is also wired into the ``schemagraph.exporters`` entry-point
group via ``pyproject.toml``, so calling code can resolve them by name:

    from schemagraph import export
    export(diagram, format="spice", path="rc.cir")
"""

from schemagraph.domain_exporters.fenics_exporter import FEniCSExporter
from schemagraph.domain_exporters.modelica_exporter import ModelicaExporter
from schemagraph.domain_exporters.openfoam_exporter import OpenFOAMExporter
from schemagraph.domain_exporters.orbital_exporter import OrbitalExporter
from schemagraph.domain_exporters.spice_exporter import SPICEExporter
from schemagraph.domain_exporters.urdf_exporter import URDFExporter
from schemagraph.registry import exporter_registry

# Register built-in domain exporters (third-party plugins still override these by name).
exporter_registry.register("spice", SPICEExporter)
exporter_registry.register("urdf", URDFExporter)
exporter_registry.register("modelica", ModelicaExporter)
exporter_registry.register("fenics", FEniCSExporter)
exporter_registry.register("openfoam", OpenFOAMExporter)
exporter_registry.register("orbital", OrbitalExporter)

__all__ = [
    "SPICEExporter",
    "URDFExporter",
    "ModelicaExporter",
    "FEniCSExporter",
    "OpenFOAMExporter",
    "OrbitalExporter",
]
