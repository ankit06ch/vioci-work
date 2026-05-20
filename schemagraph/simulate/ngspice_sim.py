"""ngspice adapter.

Generates a SPICE netlist via :class:`schemagraph.domain_exporters.SPICEExporter`,
appends a transient/AC/DC analysis block (configurable), then invokes
``ngspice`` in batch mode and parses its raw output.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from schemagraph.domain_exporters.spice_exporter import SPICEExporter
from schemagraph.ir import ids as _ids
from schemagraph.ir.schema import Dataset, DatasetSeries, Diagram, Provenance
from schemagraph.simulate.base import SimulationResult, Simulator


class NgSpiceSimulator(Simulator):
    name = "ngspice"
    domain = "electrical"

    def healthcheck(self) -> tuple[bool, str]:
        path = shutil.which("ngspice")
        if path is None:
            return False, "ngspice binary not found on PATH"
        return True, path

    def run(
        self,
        diagram: Diagram,
        *,
        parameters: Mapping[str, Any] | None = None,
        analysis: str = ".tran 0.1ms 5ms",
        probes: tuple[str, ...] = ("v(1)",),
        timeout_s: float = 30.0,
        **options: Any,
    ) -> SimulationResult:
        avail, msg = self.healthcheck()
        if not avail:
            return SimulationResult(engine=self.name, success=False, log=msg)

        effective = self._resolve(diagram, parameters)
        netlist = SPICEExporter().export(effective).rstrip()
        # ngspice expects the analysis & print directives *before* .end
        netlist = netlist.replace(".end", "").rstrip()
        netlist += f"\n{analysis}\n.print tran {' '.join(probes)}\n.end\n"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cir = td_path / "circuit.cir"
            log = td_path / "out.log"
            cir.write_text(netlist, encoding="utf-8")
            try:
                proc = subprocess.run(
                    ["ngspice", "-b", "-o", str(log), str(cir)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    env={**os.environ, "SPICE_NO_DATASEG_CHECK": "1"},
                )
            except subprocess.TimeoutExpired as e:
                return SimulationResult(
                    engine=self.name, success=False, log=f"ngspice timed out after {timeout_s}s"
                )

            log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
            full_log = (proc.stdout or "") + (proc.stderr or "") + log_text
            if proc.returncode != 0:
                return SimulationResult(
                    engine=self.name, success=False, log=full_log[:50_000]
                )

            datasets = _parse_print_output(log_text, probes, diagram)
            return SimulationResult(
                engine=self.name,
                success=True,
                datasets=datasets,
                log=full_log[:50_000],
                metadata={"analysis": analysis, "probes": list(probes)},
            )


_PRINT_RE = re.compile(r"^\s*(\d+)\s+(.+)$")


def _parse_print_output(text: str, probes: tuple[str, ...], diagram: Diagram) -> list[Dataset]:
    """Best-effort parse of ngspice `.print tran` columnar output."""
    if not text:
        return []
    lines = text.splitlines()
    # Find the header row containing "Index" and "time"
    start = None
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if low.startswith("index") and "time" in low:
            start = i
            break
    if start is None:
        return []

    rows: list[list[float]] = []
    for line in lines[start + 2 :]:
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        if "ngspice" in line.lower() or "----" in line:
            break
        m = _PRINT_RE.match(line)
        if not m:
            continue
        parts = [p for p in line.split() if p]
        try:
            vals = [float(p) for p in parts[1:]]  # drop index
        except ValueError:
            continue
        rows.append(vals)

    if not rows:
        return []
    cols = list(zip(*rows))
    if not cols:
        return []

    t_series = list(cols[0])
    series: list[DatasetSeries] = []
    for i, probe in enumerate(probes):
        if i + 1 >= len(cols):
            break
        series.append(DatasetSeries(name=probe, values=list(cols[i + 1])))
    series.insert(0, DatasetSeries(name="time", values=t_series))

    return [
        Dataset(
            id=_ids.dataset_id(diagram.id, "ngspice_tran", ["time"] + list(probes)),
            name="ngspice_tran",
            axes=["time"] + list(probes),
            series=series,
            provenance=Provenance(stage="annotator", producer="NgSpiceSimulator"),
        )
    ]
