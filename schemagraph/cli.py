"""``schemagraph`` command-line interface.

A thin wrapper over :mod:`schemagraph.api`. Run ``schemagraph --help`` for
the full command tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import schemagraph as sg  # noqa: F401  (ensures registries populate)
from schemagraph.api import annotate as _annotate
from schemagraph.api import export as _export
from schemagraph.api import parse as _parse
from schemagraph.api import validate as _validate
from schemagraph.ir.schema import Diagram
from schemagraph.registry import (
    annotator_registry,
    exporter_registry,
    list_plugins,
    provider_registry,
)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="schemagraph: diagram -> structured IR -> interoperable graph exports.",
)

providers_app = typer.Typer(help="Inspect VLM providers")
exporters_app = typer.Typer(help="Inspect exporters")
annotators_app = typer.Typer(help="Inspect physics annotators")
simulators_app = typer.Typer(help="Inspect simulators")
app.add_typer(providers_app, name="providers")
app.add_typer(exporters_app, name="exporters")
app.add_typer(annotators_app, name="annotators")
app.add_typer(simulators_app, name="simulators")

# Spacecraft instrument subcommands + REPL.
from schemagraph.instruments.cli import instrument_app, shell_app  # noqa: E402

app.add_typer(instrument_app, name="instrument")
app.add_typer(shell_app, name="shell")

console = Console()


def _load_diagram(path: Path) -> Diagram:
    return Diagram.model_validate_json(path.read_text(encoding="utf-8"))


def _save_diagram(diagram: Diagram, path: Path) -> None:
    path.write_text(diagram.model_dump_json(indent=2), encoding="utf-8")


@app.command()
def parse(
    input: Path = typer.Argument(..., exists=True, readable=True),
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d"),
    page: int = typer.Option(1, "--page"),
    out: Path = typer.Option(Path("diagram.json"), "--out", "-o"),
    no_cv: bool = typer.Option(False, "--no-cv"),
    no_ocr: bool = typer.Option(False, "--no-ocr"),
    prompt_variant: str = typer.Option("default", "--prompt-variant"),
    handdrawn: bool = typer.Option(
        False,
        "--handdrawn",
        help="use hand-drawn-tuned preprocessing (perspective correction, adaptive threshold) and prompt variant",
    ),
):
    """Parse an image/PDF/SVG into a validated Diagram JSON."""
    diagram = _parse(
        input,
        provider=provider,
        domain=domain,
        page=page,
        run_cv=not no_cv,
        run_ocr=not no_ocr,
        prompt_variant=prompt_variant,
        handdrawn=handdrawn,
    )
    _save_diagram(diagram, out)
    console.print(
        f"[green]parsed[/] [bold]{input}[/] -> {out}  "
        f"nodes={len(diagram.nodes)} edges={len(diagram.edges)}"
    )


@app.command()
def validate(diagram_json: Path = typer.Argument(..., exists=True, readable=True)):
    """Validate an IR Diagram JSON."""
    diagram = _load_diagram(diagram_json)
    report = _validate(diagram)
    for issue in report.issues:
        style = {"error": "red", "warning": "yellow", "info": "cyan"}.get(issue.severity, "white")
        console.print(f"[{style}]{issue.severity.upper()}[/] {issue.code}: {issue.message}")
    if report.ok:
        console.print("[green]ok[/]")
    else:
        sys.exit(1)


@app.command()
def annotate(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    domain: str = typer.Option("generic", "--domain", "-d"),
    out: Path = typer.Option(Path("diagram.annotated.json"), "--out", "-o"),
):
    """Apply a physics annotator (units, equations, parametric placeholders)."""
    diagram = _load_diagram(diagram_json)
    annotated = _annotate(diagram, domain=domain)
    _save_diagram(annotated, out)
    console.print(f"[green]annotated[/] domain={domain} -> {out}")


@app.command()
def apply(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    overrides: list[str] = typer.Option(
        ..., "--set", "-s", help="parameter overrides, e.g. -s R=22kohm -s C=470nF"
    ),
    out: Path = typer.Option(Path("diagram.applied.json"), "--out", "-o"),
):
    """Apply parameter overrides (name=value, name=value, ...) to a Diagram."""
    from schemagraph.physics.parametric import apply_parameters

    diagram = _load_diagram(diagram_json)
    parsed: dict[str, str] = {}
    for kv in overrides:
        if "=" not in kv:
            raise typer.BadParameter(f"expected name=value, got {kv!r}")
        k, v = kv.split("=", 1)
        parsed[k.strip()] = v.strip()
    updated = apply_parameters(diagram, parsed)
    _save_diagram(updated, out)
    console.print(f"[green]applied[/] {len(parsed)} override(s) -> {out}")


@app.command()
def export(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    fmt: str = typer.Option(..., "--format", "-f"),
    out: Path = typer.Option(..., "--out", "-o"),
):
    """Export an IR Diagram JSON to a target format."""
    diagram = _load_diagram(diagram_json)
    written = _export(diagram, format=fmt, path=out)
    console.print(f"[green]exported[/] format={fmt} -> {written}")


@app.command()
def eval(
    dataset: Path = typer.Option(..., "--dataset", exists=True, file_okay=False, dir_okay=True),
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d"),
    report: Optional[Path] = typer.Option(None, "--report", "-r"),
    json_out: Optional[Path] = typer.Option(None, "--json"),
):
    """Run the golden-fixture eval harness over a dataset directory."""
    from schemagraph.eval.harness import evaluate_dataset, report_to_json_text
    from schemagraph.eval.report import render_html

    eval_report = evaluate_dataset(dataset, provider=provider, domain=domain)
    summary = eval_report.summary()
    console.print(
        "[bold]eval summary[/]\n"
        f"  provider:        {summary['provider']}\n"
        f"  fixtures:        {summary['n_fixtures']}\n"
        f"  node F1:         {summary['node_f1']:.3f}\n"
        f"  edge F1:         {summary['edge_f1']:.3f}\n"
        f"  label accuracy:  {summary['label_accuracy']:.3f}\n"
        f"  value accuracy:  {summary['value_accuracy']:.3f}"
    )
    if json_out:
        json_out.write_text(report_to_json_text(eval_report), encoding="utf-8")
        console.print(f"[green]wrote JSON[/] {json_out}")
    if report:
        report.write_text(render_html(eval_report), encoding="utf-8")
        console.print(f"[green]wrote HTML report[/] {report}")


@app.command()
def schema(out: Optional[Path] = typer.Option(None, "--out", "-o")):
    """Print or write the IR JSON Schema."""
    js = Diagram.model_json_schema()
    text = json.dumps(js, indent=2)
    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"[green]wrote[/] {out}")
    else:
        console.print_json(text)


@app.command(name="plugins")
def plugins_cmd():
    """List all registered plugins (exporters, providers, annotators)."""
    plugins = list_plugins()
    for group, items in plugins.items():
        table = Table(title=group)
        table.add_column("name")
        for n in items:
            table.add_row(n)
        console.print(table)


@providers_app.command("list")
def providers_list():
    for n in provider_registry.names():
        console.print(n)


@exporters_app.command("list")
def exporters_list():
    for n in exporter_registry.names():
        console.print(n)


@annotators_app.command("list")
def annotators_list():
    for n in annotator_registry.names():
        console.print(n)


@simulators_app.command("list")
def simulators_list():
    from schemagraph.simulate import list_simulators

    for n in list_simulators():
        console.print(n)


@app.command(name="simulate")
def simulate_cmd(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    engine: str = typer.Option(..., "--engine", "-e"),
    set_params: list[str] = typer.Option(
        None, "--set", "-s", help="parameter overrides, e.g. -s R=22kohm"
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="write result JSON"),
):
    """Run a simulator over an IR Diagram JSON."""
    from schemagraph.simulate import simulate

    diagram = _load_diagram(diagram_json)
    overrides: dict[str, str] = {}
    for kv in set_params or []:
        if "=" not in kv:
            raise typer.BadParameter(f"expected name=value, got {kv!r}")
        k, v = kv.split("=", 1)
        overrides[k.strip()] = v.strip()

    result = simulate(diagram, engine=engine, parameters=overrides or None)
    if not result.success:
        console.print(f"[red]simulation failed:[/] {result.log[:500]}")
        sys.exit(2)
    console.print(
        f"[green]simulation ok[/] engine={engine} datasets={len(result.datasets)} "
        f"metadata={result.metadata}"
    )
    if out:
        payload = {
            "engine": result.engine,
            "success": result.success,
            "metadata": result.metadata,
            "artifacts": result.artifacts,
            "datasets": [
                {
                    "name": d.name,
                    "axes": d.axes,
                    "series": [{"name": s.name, "values": s.values} for s in d.series],
                }
                for d in result.datasets
            ],
        }
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        console.print(f"[green]wrote[/] {out}")


if __name__ == "__main__":
    app()
