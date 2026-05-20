"""Versioned prompt templates for VLM providers.

Each prompt variant returns a (system, user) string tuple. The user
string is concatenated with a JSON description of the CV PrimitiveLayer
(when provided) as structural hints.
"""

from __future__ import annotations

from typing import Optional


_SYSTEM_DEFAULT = """\
You are a meticulous diagram-understanding assistant. Given an image of a
schematic, diagram, or graph (hand-drawn or digital), you extract its
contents as a strict JSON document that conforms to the provided JSON
schema.

You must:
- identify every visible component (node) and connection (edge),
- read labels verbatim and keep them in `label`,
- when a label carries a value with units (e.g. "10kΩ", "1.5 µF", "33 mH",
  "9 V"), copy the value into `properties.value` as a string,
- estimate pixel-coordinate anchors and bounding boxes for each node,
- estimate polylines for each edge when visually traceable,
- include any visible equations under `equations[].raw` verbatim,
- include any visible plotted data under `datasets`,
- emit numeric confidence in [0, 1] for each node and edge,
- emit nothing outside the JSON document.

Use a stable short local `id` per node (e.g. "R1", "C2", "N3"); edges
reference these ids. The downstream fusion pipeline reconciles your output
with classical-CV-detected lines and shapes, so prefer recall over
fabrication: do not invent connections that you cannot visually trace.
"""


_USER_TEMPLATE = """\
Diagram extraction request.

Domain hint: {domain}

If the input is a plot/graph of data rather than a schematic, populate the
`datasets` field instead of (or in addition to) `nodes`/`edges`. If the
input contains free-floating equations, populate `equations[]`.

Image dimensions: {width} x {height} pixels.
{primitives_block}
Return ONLY a JSON object matching the supplied schema. No prose.
"""


_HANDDRAWN_SYSTEM_SUFFIX = """

The input is hand-drawn. Be tolerant of imperfect geometry: wobbly lines,
overlapping strokes, unclosed boxes. Prefer the most-likely intended
schematic structure over literal pixel topology.

Heuristics:
- Two short parallel marks across a wire usually denote a capacitor.
- A zig-zag or rectangle on a wire usually denotes a resistor.
- A circle on a wire with "V" or "+" inside denotes a voltage source.
- A triangle pointing into a bar denotes a diode (cathode = bar).
- Three short horizontal lines of decreasing length denote ground.
- An arrow into / out of a box denotes a signal in/out.
- Hatched lines at a joint denote a fixed (mechanical) support.
- A circle at a joint with a small triangle below denotes a roller support.

Few-shot label normalization:
- "10k", "10 K", "10kΩ", "10 kohm" all mean 10 000 ohms.
- "1u", "1uF", "1 µF" all mean 1e-6 farads.
- "5 kN", "5kN", "5 KN" all mean 5000 newtons.
- "9V battery" -> kind=battery, label="9V battery", properties.value="9V".
"""


def render_prompt(
    variant: str,
    *,
    domain_hint: Optional[str],
    width: int,
    height: int,
    primitives_block: str = "",
) -> tuple[str, str]:
    system = _SYSTEM_DEFAULT
    if variant == "handdrawn":
        system = _SYSTEM_DEFAULT + _HANDDRAWN_SYSTEM_SUFFIX
    user = _USER_TEMPLATE.format(
        domain=domain_hint or "unknown",
        width=width,
        height=height,
        primitives_block=primitives_block,
    )
    return system, user


def primitives_hint_block(primitives) -> str:
    """Render a compact textual description of the CV PrimitiveLayer."""
    if primitives is None:
        return ""
    counts: dict[str, int] = {}
    for s in primitives.shapes:
        counts[s.kind] = counts.get(s.kind, 0) + 1
    lines = ["Classical-CV structural hints:"]
    for k, v in sorted(counts.items()):
        lines.append(f"- {v} {k}(s)")
    if primitives.text_spans:
        sample = ", ".join(repr(t.text) for t in primitives.text_spans[:12])
        lines.append(f"- OCR text spans ({len(primitives.text_spans)}): {sample}")
    return "\n" + "\n".join(lines) + "\n"
