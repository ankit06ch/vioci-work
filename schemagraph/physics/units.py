"""Unit-aware quantity handling backed by `pint`.

This module is intentionally tolerant of messy real-world tokens like
``"10kΩ"``, ``"1.5 µF"``, ``"33 mH"``, ``"2.5e-3 N·m"``, ``"1k"`` (with a
domain default), and falls back gracefully when units cannot be inferred.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    import pint

    UREG = pint.UnitRegistry()
    # Common shorthands users write that pint doesn't know by default.
    UREG.define("ohm_symbol = ohm")
    UREG.define("@alias ohm = Ω = Ohms = ohms")
    UREG.define("@alias farad = F")
    UREG.define("@alias henry = H")
    UREG.define("@alias volt = V")
    UREG.define("@alias ampere = A")
    UREG.define("@alias hertz = Hz")
    _PINT_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when pint isn't usable
    UREG = None  # type: ignore[assignment]
    _PINT_AVAILABLE = False


from schemagraph.ir.schema import Quantity


_UNICODE_REPLACEMENTS = {
    "Ω": "ohm",
    "μ": "u",
    "µ": "u",
    "·": "*",
    "×": "*",
    "−": "-",
    "Ω": "ohm",
}


_QUANTITY_RE = re.compile(
    r"""
    ^\s*
    (?P<value>[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)
    \s*
    (?P<unit>.*?)
    \s*$
    """,
    re.VERBOSE,
)


_SI_PREFIXES = {
    "Y": 1e24, "Z": 1e21, "E": 1e18, "P": 1e15, "T": 1e12, "G": 1e9, "M": 1e6,
    "k": 1e3, "h": 1e2, "da": 1e1,
    "d": 1e-1, "c": 1e-2, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12,
    "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24,
}


def _strip_unicode(s: str) -> str:
    for k, v in _UNICODE_REPLACEMENTS.items():
        s = s.replace(k, v)
    return s


def parse_quantity_string(text: str, default_unit: Optional[str] = None) -> Optional[Quantity]:
    """Parse a free-form quantity string like ``"10kΩ"`` into a :class:`Quantity`.

    If ``default_unit`` is provided and the input has no recognizable unit
    (e.g. ``"10k"``), it is applied (so ``"10k"`` with default ``"ohm"``
    yields ``10000 ohm``).
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None

    normalized = _strip_unicode(raw)
    # If the string has a "name = value" or "name: value" prefix (common in
    # VLM-extracted labels like "R = 10kΩ"), try parsing what follows.
    for sep in ("=", ":"):
        if sep in normalized:
            tail = normalized.rsplit(sep, 1)[-1].strip()
            if tail and tail != normalized:
                tail_match = _QUANTITY_RE.match(tail)
                if tail_match and tail_match.group("value"):
                    normalized = tail
                    break
    m = _QUANTITY_RE.match(normalized)
    if not m:
        return Quantity(value=float("nan"), raw=raw)

    value = float(m.group("value"))
    unit = m.group("unit").strip() or None

    if unit is None and default_unit is not None:
        return Quantity(value=value, unit=default_unit, raw=raw)

    if unit is None:
        return Quantity(value=value, raw=raw)

    # Try splitting a leading SI prefix from the unit (e.g. "kohm", "uF", "mH",
    # or a lone "k" when a default unit is supplied for the domain).
    multiplier = 1.0
    canonical_unit = unit

    if unit == "k" or unit == "K":  # ambiguous: prefix-only vs kelvin
        # prefer prefix-only when caller supplied a default unit
        if default_unit is not None and unit == "k":
            multiplier = _SI_PREFIXES["k"]
            canonical_unit = default_unit
    elif len(unit) >= 2 and unit[:2] in _SI_PREFIXES and len(unit) > 2:
        multiplier = _SI_PREFIXES[unit[:2]]
        canonical_unit = unit[2:]
    elif unit[:1] in _SI_PREFIXES and len(unit) > 1:
        prefix = unit[:1]
        rest = unit[1:]
        if rest.lower() not in {"g", "l"}:
            multiplier = _SI_PREFIXES[prefix]
            canonical_unit = rest
    elif len(unit) == 1 and unit in _SI_PREFIXES and default_unit is not None:
        multiplier = _SI_PREFIXES[unit]
        canonical_unit = default_unit

    canonical_unit = canonical_unit.strip()
    if not canonical_unit and default_unit is not None:
        canonical_unit = default_unit

    if _PINT_AVAILABLE and canonical_unit:
        try:
            q = UREG.Quantity(value * multiplier, canonical_unit)
            return Quantity(value=float(q.magnitude), unit=str(q.units), raw=raw)
        except Exception:
            pass

    return Quantity(value=value * multiplier, unit=canonical_unit or None, raw=raw)


def coerce_quantity(value, default_unit: Optional[str] = None) -> Optional[Quantity]:
    """Convert raw VLM/JSON output to a Quantity, leaving non-numeric values alone."""
    if value is None:
        return None
    if isinstance(value, Quantity):
        if value.unit is None and default_unit is not None:
            return Quantity(value=value.value, unit=default_unit, raw=value.raw)
        return value
    if isinstance(value, (int, float)):
        return Quantity(value=float(value), unit=default_unit)
    if isinstance(value, dict) and "value" in value:
        try:
            return Quantity(**value)
        except Exception:
            pass
    if isinstance(value, str):
        return parse_quantity_string(value, default_unit=default_unit)
    return None


def normalize_quantity(q: Quantity, target_unit: str) -> Optional[Quantity]:
    """Convert a Quantity to ``target_unit`` if dimensionally compatible."""
    if not _PINT_AVAILABLE or q.unit is None:
        return None
    try:
        converted = UREG.Quantity(q.value, q.unit).to(target_unit)
        return Quantity(value=float(converted.magnitude), unit=target_unit, raw=q.raw)
    except Exception:
        return None
