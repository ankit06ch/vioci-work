"""Equation parsing utilities.

Wraps sympy to convert raw text/LaTeX equations into canonical sympy
expressions, identify free symbols, and bind symbols to IR property paths
("<node_id>.<property>"). Used by physics annotators to attach equations
to the graph so downstream optimization / reasoning systems can resolve
symbol values from node properties or user-supplied parameters.
"""

from __future__ import annotations

from typing import Iterable, Optional

try:
    import sympy
    from sympy.parsing.latex import parse_latex
    from sympy.parsing.sympy_parser import parse_expr

    _SYMPY_AVAILABLE = True
except Exception:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    parse_latex = None  # type: ignore[assignment]
    parse_expr = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False


def parse_equation(raw: str) -> tuple[Optional[str], list[str], Optional[str], Optional[str]]:
    """Return ``(sympy_repr, free_symbols, lhs_str, rhs_str)`` for a raw equation.

    Tries LaTeX first (cheap to detect via backslashes / ``$``), then falls
    back to a plain sympy expression. Returns ``(None, [], None, None)``
    on failure. For a bare expression (no ``=``), ``lhs`` is ``None`` and
    the full expression is returned as ``rhs``.
    """
    if not _SYMPY_AVAILABLE:
        return None, [], None, None
    raw = (raw or "").strip().strip("$")
    if not raw:
        return None, [], None, None

    lhs_str: Optional[str] = None
    rhs_str: Optional[str] = None
    expr = None

    if "\\" in raw or "{" in raw:
        try:
            expr = parse_latex(raw)
        except Exception:
            expr = None

    if expr is None:
        try:
            if "=" in raw:
                lhs_str, rhs_str = (s.strip() for s in raw.split("=", 1))
                expr = sympy.Eq(parse_expr(lhs_str), parse_expr(rhs_str))
            else:
                rhs_str = raw
                expr = parse_expr(raw)
        except Exception:
            return None, [], None, None
    else:
        if hasattr(expr, "lhs") and hasattr(expr, "rhs"):
            lhs_str = str(expr.lhs)
            rhs_str = str(expr.rhs)
        else:
            rhs_str = str(expr)

    try:
        symbols = sorted({str(s) for s in expr.free_symbols})  # type: ignore[union-attr]
    except Exception:
        symbols = []
    return str(expr), symbols, lhs_str, rhs_str


def resolve_variables(
    symbol_names: Iterable[str],
    *,
    nodes: list,
    parameters: list,
) -> dict[str, str]:
    """Bind sympy symbol names to IR property paths.

    Resolution order, case-insensitively:

    1. A :class:`Parameter` with matching ``name`` -> ``<param.id>.value``.
    2. A :class:`Node` with ``label`` exactly equal to the symbol -> ``<node.id>.value``.
    3. A :class:`Node` with ``label`` starting with the symbol -> ``<node.id>.value``.
    """
    out: dict[str, str] = {}
    param_by_name = {p.name.lower(): p for p in parameters}
    nodes_by_label = {(n.label or "").lower(): n for n in nodes if n.label}
    for sym in symbol_names:
        low = sym.lower()
        if low in param_by_name:
            out[sym] = f"{param_by_name[low].id}.value"
            continue
        if low in nodes_by_label:
            out[sym] = f"{nodes_by_label[low].id}.value"
            continue
        # prefix match (e.g. label "R = 10k" -> symbol "R")
        for label, node in nodes_by_label.items():
            if label.startswith(low + " ") or label == low or label.startswith(low + "="):
                out[sym] = f"{node.id}.value"
                break
    return out
