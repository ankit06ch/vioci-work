"""Axis labels and schematic lines are not bill-of-materials components."""

from __future__ import annotations

from server.annotation_service import (
    is_axis_reference_label,
    seed_from_diagram,
    should_skip_diagram_node_for_components,
)


def test_axis_reference_labels():
    assert is_axis_reference_label("+X")
    assert is_axis_reference_label("+ x")
    assert is_axis_reference_label("-Y")
    assert is_axis_reference_label("Z")
    assert is_axis_reference_label("x")
    assert not is_axis_reference_label("Solar Array")
    assert not is_axis_reference_label("X-Band Antenna")


def test_seed_skips_axis_and_unlabeled_lines():
    diagram = {
        "nodes": [
            {"id": "axis", "kind": "line", "label": "+X"},
            {"id": "wire", "kind": "line", "label": None},
            {
                "id": "cam",
                "kind": "instrument",
                "label": "Multispectral Scanner",
                "properties": {"display_name": "Multispectral Scanner"},
            },
        ]
    }
    parts = seed_from_diagram(diagram)
    assert len(parts) == 1
    assert parts[0].name == "Multispectral Scanner"
    assert should_skip_diagram_node_for_components(diagram["nodes"][0])
    assert should_skip_diagram_node_for_components(diagram["nodes"][1])
