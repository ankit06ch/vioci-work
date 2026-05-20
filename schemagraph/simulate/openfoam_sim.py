"""OpenFOAM simulator adapter (stub).

Materializes an OpenFOAM case via :class:`OpenFOAMExporter`, then invokes
``blockMesh`` followed by the requested solver binary (default
``simpleFoam``). Heavy: most users will treat this as a launch helper
rather than a synchronous call.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from schemagraph.domain_exporters.openfoam_exporter import OpenFOAMExporter
from schemagraph.ir.schema import Diagram
from schemagraph.simulate.base import SimulationResult, Simulator


class OpenFOAMSimulator(Simulator):
    name = "openfoam"
    domain = "fluid"

    def healthcheck(self) -> tuple[bool, str]:
        for tool in ("blockMesh", "simpleFoam"):
            if not shutil.which(tool):
                return False, f"{tool!r} not on PATH (source OpenFOAM bashrc first)"
        return True, "OpenFOAM tools available"

    def run(
        self,
        diagram: Diagram,
        *,
        parameters: Mapping[str, Any] | None = None,
        solver: str = "simpleFoam",
        case_path: Path | None = None,
        timeout_s: float = 600.0,
        **options: Any,
    ) -> SimulationResult:
        avail, msg = self.healthcheck()
        if not avail:
            return SimulationResult(engine=self.name, success=False, log=msg)

        effective = self._resolve(diagram, parameters)
        if case_path is None:
            case_path = Path(tempfile.mkdtemp(prefix="schemagraph-of-"))
        OpenFOAMExporter().write(effective, case_path)

        log_chunks: list[str] = []
        for cmd in ("blockMesh", solver):
            try:
                proc = subprocess.run(
                    [cmd, "-case", str(case_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                return SimulationResult(
                    engine=self.name, success=False, log=f"{cmd} timed out after {timeout_s}s"
                )
            log_chunks.append(f"$ {cmd}\n{proc.stdout}{proc.stderr}")
            if proc.returncode != 0:
                return SimulationResult(
                    engine=self.name, success=False, log="\n".join(log_chunks)[:80_000]
                )

        return SimulationResult(
            engine=self.name,
            success=True,
            log="\n".join(log_chunks)[:80_000],
            artifacts={"case_path": str(case_path)},
            metadata={"solver": solver},
        )
