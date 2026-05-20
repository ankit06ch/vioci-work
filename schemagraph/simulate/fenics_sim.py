"""FEniCS / dolfinx simulator adapter (stub).

Because FEniCS deployments vary widely (different installs, MPI, etc.),
this adapter shells out to a user-supplied Python interpreter that has
``dolfinx`` available. By default it writes the auto-generated skeleton
from :class:`FEniCSExporter` and runs it; users override
``script_path`` to point at their own driver.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from schemagraph.domain_exporters.fenics_exporter import FEniCSExporter
from schemagraph.ir.schema import Diagram
from schemagraph.simulate.base import SimulationResult, Simulator


class FEniCSSimulator(Simulator):
    name = "fenics"
    domain = "thermal"  # also: structural, fluid

    def healthcheck(self) -> tuple[bool, str]:
        # Probe for dolfinx in *some* python interpreter on PATH.
        candidates = [sys.executable, shutil.which("python3"), shutil.which("python")]
        for c in candidates:
            if not c:
                continue
            try:
                proc = subprocess.run(
                    [c, "-c", "import dolfinx"],
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    return True, c
            except Exception:
                continue
        return False, "no Python interpreter with dolfinx found"

    def run(
        self,
        diagram: Diagram,
        *,
        parameters: Mapping[str, Any] | None = None,
        script_path: Path | None = None,
        timeout_s: float = 120.0,
        **options: Any,
    ) -> SimulationResult:
        avail, msg = self.healthcheck()
        if not avail:
            return SimulationResult(engine=self.name, success=False, log=msg)
        py = msg

        effective = self._resolve(diagram, parameters)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            if script_path is None:
                script_path = td_path / "run.py"
                script_path.write_text(
                    FEniCSExporter().export(effective), encoding="utf-8"
                )
            try:
                proc = subprocess.run(
                    [py, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    cwd=td_path,
                )
            except subprocess.TimeoutExpired:
                return SimulationResult(
                    engine=self.name, success=False, log=f"timed out after {timeout_s}s"
                )
            success = proc.returncode == 0
            return SimulationResult(
                engine=self.name,
                success=success,
                log=(proc.stdout + proc.stderr)[:50_000],
                metadata={"script": str(script_path)},
            )
