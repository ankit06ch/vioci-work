"""OpenFOAM case-skeleton exporter.

Produces a ``dict[str, str]`` whose keys are relative case-paths and whose
values are file contents (or, when used via :meth:`write`, a directory is
populated). For v1 we emit ``system/controlDict``, ``system/blockMeshDict``
(minimal), ``constant/transportProperties``, and a ``0/U`` placeholder.
The intent is that a user can drop the result into an OpenFOAM working
directory and iterate from there.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemagraph.export.base import Exporter
from schemagraph.ir.schema import Diagram


_CONTROL_DICT = """\
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         1000;
deltaT          1;
writeControl    timeStep;
writeInterval   100;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
"""


_TRANSPORT = """\
FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }
transportModel  Newtonian;
nu              [0 2 -1 0 0 0 0] 1.5e-05;
"""


class OpenFOAMExporter(Exporter):
    name = "openfoam"
    default_extension = "tar"  # only used if user picks a single-file output
    binary = False

    def export(self, diagram: Diagram, **options: Any) -> dict[str, str]:
        files: dict[str, str] = {
            "system/controlDict": _CONTROL_DICT,
            "constant/transportProperties": _TRANSPORT,
            "system/blockMeshDict": self._block_mesh(diagram),
            "0/U": _initial_field("U", [0, 0, 0]),
            "0/p": _initial_field("p", 0.0),
            "system/notes.json": json.dumps(self._notes(diagram), indent=2),
        }
        return files

    def write(self, diagram: Diagram, path, **options: Any) -> Path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        for rel, body in self.export(diagram, **options).items():
            target = path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    def _block_mesh(self, diagram: Diagram) -> str:
        # Bounding box of node geometry (pixels) -> normalized to [0, 1]
        if diagram.geometry_layer:
            W, H = diagram.geometry_layer.width_px, diagram.geometry_layer.height_px
        elif diagram.primitives:
            W, H = float(diagram.primitives.width_px), float(diagram.primitives.height_px)
        else:
            W, H = 100.0, 100.0
        sx, sy = 1.0, max(0.1, H / W)
        return f"""\
FoamFile {{ version 2.0; format ascii; class dictionary; object blockMeshDict; }}
convertToMeters 1;
vertices
(
    (0 0 0) ({sx:g} 0 0) ({sx:g} {sy:g} 0) (0 {sy:g} 0)
    (0 0 1) ({sx:g} 0 1) ({sx:g} {sy:g} 1) (0 {sy:g} 1)
);
blocks ( hex (0 1 2 3 4 5 6 7) (40 40 1) simpleGrading (1 1 1) );
edges ();
boundary (
    inlet  {{ type patch; faces ((0 4 7 3)); }}
    outlet {{ type patch; faces ((1 2 6 5)); }}
    walls  {{ type wall;  faces ((0 1 5 4) (3 7 6 2)); }}
    frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }}
);
mergePatchPairs ();
"""

    def _notes(self, diagram: Diagram) -> dict:
        return {
            "diagram_id": diagram.id,
            "n_nodes": len(diagram.nodes),
            "n_edges": len(diagram.edges),
            "domain": diagram.domain,
            "parameters": [p.name for p in diagram.parameters],
        }


def _initial_field(name: str, value) -> str:
    if isinstance(value, list):
        v = f"({' '.join(str(x) for x in value)})"
        cls = "volVectorField"
    else:
        v = f"{value:g}"
        cls = "volScalarField"
    return f"""\
FoamFile {{ version 2.0; format ascii; class {cls}; object {name}; }}
internalField   uniform {v};
boundaryField
{{
    inlet  {{ type fixedValue; value uniform {v}; }}
    outlet {{ type zeroGradient; }}
    walls  {{ type fixedValue; value uniform {v}; }}
    frontAndBack {{ type empty; }}
}}
"""
