"""Tests for the spacecraft instrument feature: catalog, annotator, sheets, REPL."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from schemagraph.api import annotate as api_annotate
from schemagraph.instruments.catalog import default_catalog, load_catalog
from schemagraph.instruments.cli import _find_instrument, _Shell, _matched_nodes
from schemagraph.instruments.sheets import SheetStore, sheet_id_for
from schemagraph.ir.schema import Diagram, Node, Provenance, SourceMeta


def _prov() -> Provenance:
    return Provenance(stage="user", producer="t")


def _landsat_diagram() -> Diagram:
    """Mimics what Gemini extracted from the Landsat callout image."""
    return Diagram(
        id="dgm_landsat_test",
        source=SourceMeta(),
        domain="generic",
        nodes=[
            Node(id="n1", kind="antenna", label="High gain antenna", provenance=_prov()),
            Node(id="n2", kind="scanner", label="Multispectral scanner (MSS)", provenance=_prov()),
            Node(id="n3", kind="solar array", label="Solar array", provenance=_prov()),
            Node(id="n4", kind="antenna", label="X-band antenna", provenance=_prov()),
            Node(id="n5", kind="antenna", label="S-band antenna", provenance=_prov()),
            Node(id="n6", kind="mapper", label="Thematic Mapper (TM)", provenance=_prov()),
            Node(id="n7", kind="component", label="some unknown thing", provenance=_prov()),
        ],
    )


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------


def test_catalog_loads_known_instruments():
    cat = default_catalog()
    for key in (
        "multispectral_scanner",
        "thematic_mapper",
        "high_gain_antenna",
        "s_band_antenna",
        "x_band_antenna",
        "solar_array",
        "battery",
        "gps_receiver",
        "imu",
        "reaction_wheel",
        "star_tracker",
    ):
        assert key in cat.entries


def test_catalog_match_aliases():
    cat = default_catalog()
    assert cat.match("MSS").id == "multispectral_scanner"
    assert cat.match("Multispectral Scanner (MSS)").id == "multispectral_scanner"
    assert cat.match("TM").id == "thematic_mapper"
    assert cat.match("Thematic Mapper").id == "thematic_mapper"
    assert cat.match("High gain antenna").id == "high_gain_antenna"
    assert cat.match("S-band antenna").id == "s_band_antenna"
    assert cat.match("X-band antenna").id == "x_band_antenna"
    assert cat.match("Solar array").id == "solar_array"


def test_catalog_no_match_for_unknown():
    cat = default_catalog()
    assert cat.match("plasma propulsion thruster") is None


# ---------------------------------------------------------------------------
# annotator
# ---------------------------------------------------------------------------


def test_spacecraft_annotator_enriches_known_nodes():
    diagram = _landsat_diagram()
    annotated = api_annotate(diagram, domain="spacecraft")

    matched = _matched_nodes(annotated)
    assert {n.label for n in matched} == {
        "High gain antenna",
        "Multispectral scanner (MSS)",
        "Solar array",
        "X-band antenna",
        "S-band antenna",
        "Thematic Mapper (TM)",
    }
    mss = next(n for n in matched if "MSS" in (n.label or ""))
    props = mss.properties
    assert props["instrument_id"] == "multispectral_scanner"
    assert props["data_product"] == "raster"
    assert props["sheet_id"].startswith("multispectral_scanner.")
    schema_fields = [f["name"] for f in props["telemetry_schema"]]
    for needed in ("timestamp", "scene_id", "B1", "B2", "B3", "B4"):
        assert needed in schema_fields


def test_spacecraft_annotator_leaves_unknown_nodes_alone():
    diagram = _landsat_diagram()
    annotated = api_annotate(diagram, domain="spacecraft")
    unknown = next(n for n in annotated.nodes if n.label == "some unknown thing")
    assert "instrument_id" not in unknown.properties
    assert "telemetry_schema" not in unknown.properties


# ---------------------------------------------------------------------------
# sheets
# ---------------------------------------------------------------------------


def test_sheet_id_is_deterministic():
    a = sheet_id_for("multispectral_scanner", "n2")
    b = sheet_id_for("multispectral_scanner", "n2")
    c = sheet_id_for("multispectral_scanner", "n3")
    assert a == b
    assert a != c
    assert a.startswith("multispectral_scanner.")


def test_sheet_attach_csv_and_query_roundtrip(tmp_path: Path):
    csv_path = tmp_path / "mss.csv"
    csv_path.write_text(
        "timestamp,scene_id,lat,lon,B1,B2,B3,B4\n"
        "2024-01-01T00:00:00Z,S1,41.3,-73.99,50,60,72,90\n"
        "2024-01-02T00:00:00Z,S2,41.4,-73.95,55,68,110,120\n"
        "2024-01-03T00:00:00Z,S3,41.5,-73.90,52,64,140,135\n",
        encoding="utf-8",
    )
    store = SheetStore(tmp_path)
    sid = "multispectral_scanner.aaaa"
    n = store.attach_csv(sid, csv_path)
    assert n == 3
    assert store.count(sid) == 3
    head = store.head(sid, limit=2)
    assert head[0]["scene_id"] == "S1"
    assert isinstance(head[0]["lat"], float) and head[0]["lat"] == 41.3
    # query: numeric filter
    high_b3 = store.query(sid, where="r['B3'] > 100")
    assert {r["scene_id"] for r in high_b3} == {"S2", "S3"}
    summary = store.summary(sid)
    assert summary.rows == 3
    assert "B3" in summary.fields
    assert summary.stats["B3"]["min"] == 72
    assert summary.stats["B3"]["max"] == 140


def test_sheet_query_rejects_unsafe_expressions(tmp_path: Path):
    store = SheetStore(tmp_path)
    store.append_rows("foo.bar", [{"x": 1}])
    with pytest.raises(ValueError):
        store.query("foo.bar", where="__import__('os').system('echo hi')")


def test_sheet_missing_raises_on_query(tmp_path: Path):
    from schemagraph.instruments.sheets import SheetMissingError

    store = SheetStore(tmp_path)
    with pytest.raises(SheetMissingError):
        store.query("no_such_sheet")


# ---------------------------------------------------------------------------
# REPL helpers (we don't drive cmdloop in tests; we exercise dispatch directly)
# ---------------------------------------------------------------------------


def _save_annotated(diagram: Diagram, tmp_path: Path) -> Path:
    p = tmp_path / "landsat.annotated.json"
    p.write_text(diagram.model_dump_json(indent=2), encoding="utf-8")
    return p


def test_find_instrument_matches_by_label_and_alias(tmp_path: Path):
    diagram = api_annotate(_landsat_diagram(), domain="spacecraft")
    saved = _save_annotated(diagram, tmp_path)

    sh = _Shell(saved)
    assert _find_instrument(sh.diagram, "Multispectral Scanner").id != "n7"
    assert _find_instrument(sh.diagram, "MSS").label.startswith("Multispectral")
    assert _find_instrument(sh.diagram, "TM").label.startswith("Thematic")
    assert _find_instrument(sh.diagram, "Solar array").label == "Solar array"
    assert _find_instrument(sh.diagram, "nope") is None


def test_repl_attach_and_pull(tmp_path: Path, capsys):
    diagram = api_annotate(_landsat_diagram(), domain="spacecraft")
    saved = _save_annotated(diagram, tmp_path)

    csv_path = tmp_path / "mss.csv"
    csv_path.write_text(
        "timestamp,scene_id,B3\n2024-01-01T00:00:00Z,S1,150\n2024-01-02T00:00:00Z,S2,90\n",
        encoding="utf-8",
    )

    sh = _Shell(saved)
    sh.do_attach(f'"Multispectral Scanner" {csv_path}')
    sh.do_pull('"Multispectral Scanner"')

    out = capsys.readouterr().out
    assert "attached 2 rows" in out
    assert "S1" in out and "S2" in out


def test_repl_query_with_filter(tmp_path: Path, capsys):
    diagram = api_annotate(_landsat_diagram(), domain="spacecraft")
    saved = _save_annotated(diagram, tmp_path)
    csv_path = tmp_path / "mss.csv"
    csv_path.write_text(
        "timestamp,scene_id,B3\nA,S1,150\nB,S2,90\nC,S3,200\n",
        encoding="utf-8",
    )
    sh = _Shell(saved)
    sh.do_attach(f'"Multispectral Scanner" {csv_path}')
    sh.do_query("MSS r['B3'] > 100")
    out = capsys.readouterr().out
    assert "S1" in out
    assert "S3" in out
    assert "S2" not in out
