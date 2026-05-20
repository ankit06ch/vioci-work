"""Beam network FEA tests."""

from schemagraph.launch_compat.assembler import assemble_spacecraft
from schemagraph.launch_compat.structural.static_fea import solve_beam_fea


def test_empty_network():
    sc = assemble_spacecraft({}, [])
    fea = solve_beam_fea(sc, 6.0, 0.5)
    assert fea["fea_mode"] == "none"
