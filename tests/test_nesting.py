"""Smoke tests for pipeline/Nesting.py (bottom-left-fill nesting)."""

from __future__ import annotations

import json
import time

import pytest
from shapely.geometry import Polygon

from pipeline import Nesting, common

GAP_MM = 5.0
WIDTH_IN = 54.0


@pytest.fixture
def nested(sample_pieces_doc, write_tmp_doc, tmp_path):
    """Run the full CLI once; share the result across assertions."""
    pieces_path = write_tmp_doc(sample_pieces_doc)
    out_dir = tmp_path / "takeoff"
    t0 = time.monotonic()
    rc = Nesting.main(["--pieces", str(pieces_path),
                       "--gap-mm", str(GAP_MM),
                       "--width-in", str(WIDTH_IN),
                       "--out-dir", str(out_dir)])
    elapsed = time.monotonic() - t0
    assert rc == 0
    doc = json.loads((out_dir / "nesting.json").read_text(encoding="utf-8"))
    return {
        "doc": doc,
        "out_dir": out_dir,
        "elapsed": elapsed,
        "pieces": {p["id"]: p for p in sample_pieces_doc["pieces"]},
    }


def _placed_polygons(doc, pieces_by_id) -> list[Polygon]:
    return [Nesting.apply_placement(pieces_by_id[pl["piece_id"]]["polygon"], pl)
            for pl in doc["placements"]]


def test_all_copies_placed(nested):
    doc, pieces = nested["doc"], nested["pieces"]
    assert doc["schema"] == "3dfabric.nesting/1"
    assert doc["design"] == "unittote"
    expected = sum(p.get("cut_qty", 1) for p in pieces.values())
    assert len(doc["placements"]) == expected == 5
    got = {(pl["piece_id"], pl["copy"]) for pl in doc["placements"]}
    want = {(pid, c) for pid, p in pieces.items()
            for c in range(1, p.get("cut_qty", 1) + 1)}
    assert got == want


def test_no_pairwise_overlaps_and_gap(nested):
    polys = _placed_polygons(nested["doc"], nested["pieces"])
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j]).area
            assert inter < 1e-6, f"pieces {i} and {j} overlap by {inter} mm^2"
            # placements are rounded to 3 decimals -> small tolerance
            assert polys[i].distance(polys[j]) >= GAP_MM - 0.01


def test_pieces_inside_sheet(nested):
    doc = nested["doc"]
    polys = _placed_polygons(doc, nested["pieces"])
    sheet_w = WIDTH_IN * common.MM_PER_IN
    for p in polys:
        minx, miny, maxx, maxy = p.bounds
        assert minx >= -0.01 and miny >= -0.01
        assert maxx <= sheet_w + 0.01
        assert maxy <= doc["used_length_mm"] + 0.01


def test_utilization_and_lengths(nested):
    doc = nested["doc"]
    assert 0.0 < doc["utilization"] <= 1.0
    assert doc["used_length_mm"] > 0
    assert doc["used_length_yd"] > 0
    assert doc["used_length_in"] == pytest.approx(
        common.mm_to_in(doc["used_length_mm"]), abs=0.02)
    assert doc["used_length_yd"] == pytest.approx(
        common.in_to_yd(doc["used_length_in"]), abs=0.002)
    # used length must match the re-applied placements
    polys = _placed_polygons(doc, nested["pieces"])
    assert doc["used_length_mm"] == pytest.approx(
        max(p.bounds[3] for p in polys), abs=0.1)
    assert doc["total_piece_area_mm2"] == pytest.approx(
        sum(common.ring_area_mm2(p["polygon"]) * p.get("cut_qty", 1)
            for p in nested["pieces"].values()), rel=1e-6)
    assert "DRAFT" in doc["draft"]


def test_nested_svg_parses(nested):
    from svgpathtools import svg2paths
    svg_path = nested["out_dir"] / f"nested_{WIDTH_IN:g}in.svg"
    assert svg_path.is_file()
    paths, _attrs = svg2paths(str(svg_path))
    # one path per placed piece + the sheet outline rect, at minimum
    assert len(paths) >= len(nested["doc"]["placements"]) + 1


def test_runtime_under_60s(nested):
    assert nested["elapsed"] < 60.0


def test_svg_input_with_polygon_and_curved_path(write_tmp_doc, tmp_path):
    """--svg mode: polygons AND <path> elements (curves sampled) become pieces."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400mm" height="300mm" '
        'viewBox="0 0 400 300">\n'
        '<polygon points="10,10 110,10 110,80 10,80"/>\n'
        '<path d="M 200,50 C 260,10 320,90 380,50 L 380,120 L 200,120 Z"/>\n'
        '</svg>\n'
    )
    svg_path = write_tmp_doc(svg, name="input.svg")
    pieces = Nesting.load_pieces_from_svg(svg_path)
    assert len(pieces) == 2
    areas = sorted(Polygon(p["polygon"]).area for p in pieces)
    assert areas[0] == pytest.approx(100 * 70, rel=0.01)   # the polygon
    assert areas[1] > 180 * 70 * 0.8                       # the curvy path

    out_dir = tmp_path / "svg_takeoff"
    rc = Nesting.main(["--svg", str(svg_path), "--design", "svgdemo",
                       "--out-dir", str(out_dir)])
    assert rc == 0
    doc = json.loads((out_dir / "nesting.json").read_text(encoding="utf-8"))
    assert len(doc["placements"]) == 2
    assert (out_dir / "nested_54in.svg").is_file()


def test_stitch_lines_and_holes_dropped_from_svg(write_tmp_doc):
    """Rings contained inside a larger ring must not become pieces."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="300mm" '
        'viewBox="0 0 300 300">\n'
        '<polygon points="0,0 200,0 200,150 0,150"/>\n'
        '<polygon points="10,10 190,10 190,140 10,140"/>\n'  # stitch line
        '</svg>\n'
    )
    pieces = Nesting.load_pieces_from_svg(write_tmp_doc(svg, name="s.svg"))
    assert len(pieces) == 1
    assert Polygon(pieces[0]["polygon"]).area == pytest.approx(200 * 150, rel=0.01)
