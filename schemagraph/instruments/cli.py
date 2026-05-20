"""``schemagraph instrument …`` subcommand tree and the ``schemagraph shell`` REPL.

Kept in this subpackage (not in the top-level ``cli.py``) so the satellite
feature is fully self-contained and importable as a unit.
"""

from __future__ import annotations

import cmd
import json
import shlex
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from schemagraph.instruments.catalog import default_catalog
from schemagraph.instruments.sheets import SheetMissingError, SheetStore
from schemagraph.ir.schema import Diagram


instrument_app = typer.Typer(help="Per-instrument data sheets (load, query, summarize)")
shell_app = typer.Typer(help="Interactive shell over a parsed diagram")
console = Console()


# ---------------------------------------------------------------------------
# helpers shared by the subcommands and the REPL
# ---------------------------------------------------------------------------


def _load(diagram_json: Path) -> Diagram:
    return Diagram.model_validate_json(diagram_json.read_text(encoding="utf-8"))


def _store_for(diagram_json: Path) -> SheetStore:
    return SheetStore(diagram_json.parent)


def _find_instrument(diagram: Diagram, query: str):
    """Find a node by label / display name / instrument_id."""
    q = query.strip().lower()
    matches = []
    for n in diagram.nodes:
        props = n.properties or {}
        candidates = {
            (n.label or "").lower(),
            (props.get("display_name") or "").lower(),
            (props.get("instrument_id") or "").lower(),
            (n.kind or "").lower(),
            n.id.lower(),
        }
        if any(c == q for c in candidates if c):
            return n
        if any(q in c for c in candidates if c):
            matches.append(n)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    # Ambiguous: prefer one with an instrument_id (i.e. catalog-matched).
    for n in matches:
        if (n.properties or {}).get("instrument_id"):
            return n
    return matches[0]


def _matched_nodes(diagram: Diagram):
    return [
        n
        for n in diagram.nodes
        if (n.properties or {}).get("instrument_id") is not None
    ]


# ---------------------------------------------------------------------------
# `schemagraph instrument …` subcommands
# ---------------------------------------------------------------------------


@instrument_app.command("list")
def instrument_list(diagram_json: Path = typer.Argument(..., exists=True, readable=True)):
    """List catalog-matched instruments in a parsed diagram."""
    diagram = _load(diagram_json)
    store = _store_for(diagram_json)
    nodes = _matched_nodes(diagram)
    if not nodes:
        console.print(
            "[yellow]no catalog-matched instruments found — did you run "
            "[bold]schemagraph annotate --domain spacecraft[/]?[/]"
        )
        return
    table = Table(title="Instruments")
    table.add_column("display name")
    table.add_column("instrument id")
    table.add_column("data product")
    table.add_column("sheet rows", justify="right")
    for n in nodes:
        props = n.properties or {}
        sheet_id = props.get("sheet_id") or ""
        rows = store.count(sheet_id) if sheet_id else 0
        table.add_row(
            str(props.get("display_name") or n.label or "?"),
            str(props.get("instrument_id") or ""),
            str(props.get("data_product") or ""),
            str(rows),
        )
    console.print(table)


@instrument_app.command("show")
def instrument_show(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(..., help="instrument label, id, or display name"),
):
    """Show one instrument's schema and a few sample rows (if any)."""
    diagram = _load(diagram_json)
    store = _store_for(diagram_json)
    node = _find_instrument(diagram, query)
    if node is None:
        console.print(f"[red]no instrument matching {query!r}[/]")
        raise typer.Exit(code=1)
    props = node.properties or {}
    console.print(f"[bold]{props.get('display_name') or node.label}[/]")
    console.print(f"  instrument_id: {props.get('instrument_id')}")
    console.print(f"  data_product:  {props.get('data_product')}")
    console.print(f"  sheet_id:      {props.get('sheet_id')}")
    schema = props.get("telemetry_schema") or []
    if schema:
        table = Table(title="telemetry fields")
        table.add_column("name")
        table.add_column("unit")
        table.add_column("dtype")
        for f in schema:
            table.add_row(f.get("name", ""), f.get("unit", ""), f.get("dtype", ""))
        console.print(table)
    sheet_id = props.get("sheet_id")
    if sheet_id and store.exists(sheet_id):
        head = store.head(sheet_id, limit=3)
        console.print(f"[dim]first {len(head)} rows of {sheet_id}[/]")
        for row in head:
            console.print("  " + json.dumps(row, default=str))
    else:
        console.print("[dim]no data attached yet — use `schemagraph instrument attach`[/]")


@instrument_app.command("attach")
def instrument_attach(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(..., help="instrument label, id, or display name"),
    csv: Path = typer.Option(..., "--data", exists=True, readable=True),
):
    """Attach a CSV of telemetry to an instrument's sheet."""
    diagram = _load(diagram_json)
    store = _store_for(diagram_json)
    node = _find_instrument(diagram, query)
    if node is None:
        console.print(f"[red]no instrument matching {query!r}[/]")
        raise typer.Exit(code=1)
    sheet_id = (node.properties or {}).get("sheet_id")
    if not sheet_id:
        console.print(f"[red]instrument has no sheet_id; annotate first[/]")
        raise typer.Exit(code=1)
    n = store.attach_csv(sheet_id, csv)
    console.print(f"[green]attached[/] {n} rows -> sheet [bold]{sheet_id}[/]")


@instrument_app.command("query")
def instrument_query(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(..., help="instrument label, id, or display name"),
    where: Optional[str] = typer.Option(
        None,
        "--where",
        help="Python boolean expression over a row dict named `r`, e.g. \"r['B3']>100\"",
    ),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """Pull rows back from an instrument's sheet, with optional filter."""
    diagram = _load(diagram_json)
    store = _store_for(diagram_json)
    node = _find_instrument(diagram, query)
    if node is None:
        console.print(f"[red]no instrument matching {query!r}[/]")
        raise typer.Exit(code=1)
    sheet_id = (node.properties or {}).get("sheet_id")
    try:
        rows = store.query(sheet_id, where=where, limit=limit)
    except SheetMissingError:
        console.print(f"[yellow]no data attached for {sheet_id}[/]")
        raise typer.Exit(code=2)
    for r in rows:
        console.print(json.dumps(r, default=str))
    console.print(f"[dim]{len(rows)} rows[/]")


@instrument_app.command("summary")
def instrument_summary(
    diagram_json: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(..., help="instrument label, id, or display name"),
):
    """Per-column summary statistics for an instrument's sheet."""
    diagram = _load(diagram_json)
    store = _store_for(diagram_json)
    node = _find_instrument(diagram, query)
    if node is None:
        console.print(f"[red]no instrument matching {query!r}[/]")
        raise typer.Exit(code=1)
    sheet_id = (node.properties or {}).get("sheet_id")
    s = store.summary(sheet_id)
    console.print(f"[bold]{sheet_id}[/]  rows={s.rows}")
    table = Table()
    table.add_column("field")
    table.add_column("count", justify="right")
    table.add_column("min", justify="right")
    table.add_column("max", justify="right")
    table.add_column("mean", justify="right")
    for f in s.fields:
        st = s.stats.get(f, {})
        table.add_row(
            f,
            str(st.get("count", "")),
            _fmt(st.get("min")),
            _fmt(st.get("max")),
            _fmt(st.get("mean")),
        )
    console.print(table)


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3g}"
    return str(v)


# ---------------------------------------------------------------------------
# `schemagraph shell` REPL
# ---------------------------------------------------------------------------


class _Shell(cmd.Cmd):
    intro = (
        "schemagraph shell. Type `help` or `?` for commands; `exit` to quit.\n"
        "Try: `ls`, `describe MSS`, `pull \"Multispectral Scanner\"`."
    )
    prompt = "schemagraph> "

    def __init__(self, diagram_json: Path):
        super().__init__()
        self.diagram_json = diagram_json
        self.diagram = _load(diagram_json)
        self.store = _store_for(diagram_json)

    def _resolve(self, args: list[str]):
        if not args:
            console.print("[red]usage: <command> <instrument>[/]")
            return None
        query = " ".join(args)
        node = _find_instrument(self.diagram, query)
        if node is None:
            console.print(f"[red]no instrument matching {query!r}[/]")
        return node

    # ------- commands ----------------------------------------------
    def do_ls(self, _line: str):
        """List instruments and their sheet sizes."""
        nodes = _matched_nodes(self.diagram)
        if not nodes:
            console.print(
                "[yellow]no catalog-matched instruments — run "
                "`schemagraph annotate --domain spacecraft` first[/]"
            )
            return
        for n in nodes:
            p = n.properties
            rows = self.store.count(p.get("sheet_id") or "")
            console.print(
                f"  {p.get('display_name') or n.label:30s} "
                f"({p.get('data_product'):14s} {rows:>6d} rows)"
            )

    def do_describe(self, line: str):
        """describe <instrument>  -- show schema."""
        node = self._resolve(shlex.split(line))
        if node is None:
            return
        p = node.properties
        console.print(f"[bold]{p.get('display_name') or node.label}[/]")
        console.print(f"  data_product: {p.get('data_product')}")
        for f in p.get("telemetry_schema") or []:
            console.print(f"  - {f['name']:15s} {f.get('unit', ''):14s} {f.get('dtype', '')}")

    def do_pull(self, line: str):
        """pull <instrument> [N]  -- show first N rows (default 5)."""
        parts = shlex.split(line)
        n_arg = 5
        if parts and parts[-1].isdigit():
            n_arg = int(parts[-1])
            parts = parts[:-1]
        node = self._resolve(parts)
        if node is None:
            return
        sid = node.properties.get("sheet_id")
        try:
            rows = self.store.head(sid, limit=n_arg)
        except SheetMissingError:
            console.print(f"[yellow]no data attached for {sid}[/]")
            return
        if not rows:
            console.print(f"[yellow]sheet {sid} is empty[/]")
            return
        console.print(
            f"{self.store.count(sid)} total rows; fields: "
            + ", ".join(rows[0].keys())
        )
        for r in rows:
            console.print("  " + json.dumps(r, default=str))

    def do_attach(self, line: str):
        """attach <instrument> <csv_path>  -- load a CSV into the sheet."""
        parts = shlex.split(line)
        if len(parts) < 2:
            console.print("[red]usage: attach <instrument> <csv_path>[/]")
            return
        csv_path = Path(parts[-1])
        node = self._resolve(parts[:-1])
        if node is None:
            return
        if not csv_path.exists():
            console.print(f"[red]no such file: {csv_path}[/]")
            return
        sid = node.properties.get("sheet_id")
        n = self.store.attach_csv(sid, csv_path)
        console.print(f"[green]attached[/] {n} rows -> {sid}")

    def do_query(self, line: str):
        """query <instrument> <python-bool-expr>  -- e.g. query MSS r['B3']>100"""
        import re

        # The instrument name may contain spaces. Find the boundary directly
        # on the raw line so we don't lose quotes inside the Python expression
        # (e.g. r['B3'] would otherwise be shlex-stripped to r[B3]).
        m = re.search(r"(?:\br\[|[<>=!]=?)", line)
        if not m or m.start() == 0:
            console.print("[red]usage: query <instrument> <expr like r['B3']>100>[/]")
            return
        instrument_part = line[: m.start()].strip()
        expr = line[m.start() :].strip()
        node = self._resolve(shlex.split(instrument_part))
        if node is None:
            return
        sid = node.properties.get("sheet_id")
        try:
            rows = self.store.query(sid, where=expr, limit=20)
        except SheetMissingError:
            console.print(f"[yellow]no data attached for {sid}[/]")
            return
        except Exception as e:
            console.print(f"[red]query error: {e}[/]")
            return
        for r in rows:
            console.print(json.dumps(r, default=str))
        console.print(f"[dim]{len(rows)} rows[/]")

    def do_exit(self, _line: str):
        """Exit the shell."""
        return True

    do_quit = do_exit
    do_EOF = do_exit


@shell_app.callback(invoke_without_command=True)
def shell_entrypoint(diagram_json: Path = typer.Argument(..., exists=True, readable=True)):
    """Open an interactive REPL over a parsed (and annotated) diagram."""
    sh = _Shell(diagram_json)
    sh.cmdloop()
