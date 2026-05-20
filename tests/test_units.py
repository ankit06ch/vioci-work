"""Unit-aware quantity parsing."""

from __future__ import annotations

from schemagraph.physics.units import (
    coerce_quantity,
    normalize_quantity,
    parse_quantity_string,
)


def test_parse_si_prefix_ohms():
    q = parse_quantity_string("10kΩ")
    assert q is not None
    assert q.unit and "ohm" in q.unit
    assert abs(q.value - 10000.0) < 1e-6


def test_parse_micro_farad():
    q = parse_quantity_string("1.5 µF")
    assert q is not None
    assert q.unit and "farad" in q.unit
    assert abs(q.value - 1.5e-6) < 1e-12


def test_parse_with_default_unit():
    q = parse_quantity_string("33", default_unit="ohm")
    assert q is not None
    assert q.unit == "ohm"
    assert q.value == 33.0


def test_parse_plain_si_no_unit_with_default():
    q = parse_quantity_string("10k", default_unit="ohm")
    assert q is not None
    assert q.unit and "ohm" in q.unit
    assert abs(q.value - 10000.0) < 1e-6


def test_coerce_dict_quantity():
    q = coerce_quantity({"value": 5.0, "unit": "ohm"})
    assert q is not None and q.unit == "ohm" and q.value == 5.0


def test_coerce_number_with_default_unit():
    q = coerce_quantity(2.7, default_unit="volt")
    assert q is not None and q.unit == "volt" and q.value == 2.7


def test_normalize_to_target_unit():
    q = parse_quantity_string("1000 mV")
    assert q is not None
    n = normalize_quantity(q, "volt")
    assert n is not None
    assert abs(n.value - 1.0) < 1e-9
    assert n.unit == "volt"
