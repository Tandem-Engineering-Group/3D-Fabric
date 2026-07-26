"""Smoke tests for pipeline/Takeoff.py — synthetic fixtures, no Blender."""

import csv
import json
import random
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import Takeoff  # noqa: E402

MATERIALS_DOC = {
    "defaults": {"fabric_width_in": 54, "waste_factor": 0.10},
    "materials": {
        "canvas": {"display": "Test canvas 12oz", "unit": "yard",
                   "width_in": 54, "price_usd": 18.00},
        "narrow": {"display": "Narrow goods", "unit": "yard",
                   "width_in": 45, "price_usd": 10.00},
        "leather": {"display": "Test hide", "unit": "hide",
                    "sheet_w_in": 48, "sheet_h_in": 24,
                    "price_usd": 160.00},
    },
}


def nesting_doc(**overrides):
    doc = {
        "schema": "3dfabric.nesting/1",
        "design": "testbag",
        "sheet_width_in": 54.0,
        "used_length_in": 36.0,          # exactly 1 linear yard
        "utilization": 0.5,
        "total_piece_area_mm2": 400_000.0,
    }
    doc.update(overrides)
    return doc


def test_yard_goods_math():
    doc = Takeoff.compute_takeoff(nesting_doc(), "canvas", MATERIALS_DOC)
    # 36 in / 36 * 1.10 waste = 1.1 yd; 1.1 * $18 = $19.80
    assert doc["schema"] == "3dfabric.takeoff/1"
    assert doc["design"] == "testbag"
    assert doc["material"] == "canvas"
    assert doc["material_display"] == "Test canvas 12oz"
    assert doc["linear_yd_per_unit"] == pytest.approx(1.1)
    assert doc["material_cost_per_unit_usd"] == pytest.approx(19.80)
    assert doc["waste_factor"] == pytest.approx(0.10)
    assert doc["utilization"] == pytest.approx(0.5)
    assert "hides_per_unit" not in doc
    assert "DRAFT" in doc["draft"]
    assert isinstance(doc["assumptions"], list) and doc["assumptions"]


def test_narrow_roll_errors_clearly():
    with pytest.raises(ValueError, match="narrower"):
        Takeoff.compute_takeoff(nesting_doc(), "narrow", MATERIALS_DOC)


def test_roll_width_equal_to_sheet_is_ok():
    # boundary: 54 in roll on a 54 in nesting must NOT error
    doc = Takeoff.compute_takeoff(nesting_doc(sheet_width_in=54.0),
                                  "canvas", MATERIALS_DOC)
    assert doc["linear_yd_per_unit"] == pytest.approx(1.1)


def test_percent_utilization_normalized():
    doc = Takeoff.compute_takeoff(nesting_doc(utilization=55.0),
                                  "canvas", MATERIALS_DOC)
    assert doc["utilization"] == pytest.approx(0.55)
    assert any("percentage" in a for a in doc["assumptions"])


def test_missing_sheet_width_assumes_default():
    nd = nesting_doc()
    del nd["sheet_width_in"]
    doc = Takeoff.compute_takeoff(nd, "canvas", MATERIALS_DOC)
    assert doc["sheet_width_in"] == pytest.approx(54.0)
    assert any("sheet width" in a for a in doc["assumptions"])


def test_unknown_unit_errors():
    mats = {"materials": {"bolt_goods": {"unit": "bolt", "price_usd": 5.0}}}
    with pytest.raises(ValueError, match="unknown unit"):
        Takeoff.compute_takeoff(nesting_doc(), "bolt_goods", mats)


def test_hide_math_one_hide():
    # usable = 48*24*645.16*0.75 = 557418.24 mm2
    # 400000 * 1.1 = 440000 -> ceil(440000/557418.24) = 1 hide, $160
    doc = Takeoff.compute_takeoff(nesting_doc(), "leather", MATERIALS_DOC)
    assert doc["hides_per_unit"] == 1
    assert doc["material_cost_per_unit_usd"] == pytest.approx(160.00)
    assert "linear_yd_per_unit" not in doc
    assert any("hide math is an approximation" in a
               for a in doc["assumptions"])


def test_hide_math_rounds_up_to_two():
    # 600000 * 1.1 = 660000 -> ceil(660000/557418.24) = 2 hides, $320
    doc = Takeoff.compute_takeoff(
        nesting_doc(total_piece_area_mm2=600_000.0), "leather",
        MATERIALS_DOC)
    assert doc["hides_per_unit"] == 2
    assert doc["material_cost_per_unit_usd"] == pytest.approx(320.00)


def test_used_length_mm_fallback():
    doc = Takeoff.compute_takeoff(
        nesting_doc(used_length_in=None, used_length_mm=914.4),  # 36 in
        "canvas", MATERIALS_DOC)
    assert doc["linear_yd_per_unit"] == pytest.approx(1.1)


def test_unknown_material_errors():
    with pytest.raises(KeyError, match="velvet"):
        Takeoff.compute_takeoff(nesting_doc(), "velvet", MATERIALS_DOC)


def test_csv_row_per_qty_and_totals(tmp_path):
    takeoff = Takeoff.compute_takeoff(nesting_doc(), "canvas", MATERIALS_DOC)
    json_path, csv_path = Takeoff.write_outputs(takeoff, [1, 10], tmp_path)
    assert json_path.is_file() and csv_path.is_file()
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 3                       # header + 2 qty lines
    assert rows[0][0] == "design"
    assert rows[1][:3] == ["testbag", "canvas", "1"]
    assert float(rows[1][5]) == pytest.approx(19.80)
    assert rows[2][2] == "10"
    assert float(rows[2][5]) == pytest.approx(198.00)


def test_cli_end_to_end(tmp_path):
    nesting_path = tmp_path / "nesting.json"
    nesting_path.write_text(json.dumps(nesting_doc()), encoding="utf-8")
    materials_path = tmp_path / "materials.yaml"
    materials_path.write_text(yaml.safe_dump(MATERIALS_DOC),
                              encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = Takeoff.main([
        "--nesting", str(nesting_path),
        "--material", "canvas",
        "--qty", "1", "5",
        "--materials", str(materials_path),
        "--out-dir", str(out_dir),
    ])
    assert rc == 0

    doc = json.loads((out_dir / "takeoff.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "3dfabric.takeoff/1"
    assert doc["linear_yd_per_unit"] == pytest.approx(1.1)
    assert "DRAFT" in doc["draft"]
    with (out_dir / "takeoff.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 3                       # header + qty 1 + qty 5


def test_repo_price_book_prices_every_material():
    """The CLI default price book (repo materials.yaml) must stay usable:
    every entry needs the fields its unit requires, and the default
    --material canvas must exist."""
    book = Takeoff.load_materials()             # default: repo materials.yaml
    assert "canvas" in book["materials"]        # CLI default material
    for key, mat in book["materials"].items():
        unit = str(mat.get("unit", "yard")).lower()
        assert unit in ("yard", "hide"), f"{key}: unexpected unit {unit!r}"
        if unit == "hide":
            assert "sheet_w_in" in mat and "sheet_h_in" in mat, key
        # narrow rolls priced at a narrower nesting width, wide at 54
        width = float(mat.get("width_in", 54))
        doc = Takeoff.compute_takeoff(
            nesting_doc(sheet_width_in=min(width, 54.0)), key, book)
        assert doc["material_cost_per_unit_usd"] > 0, key


def test_seeded_nesting_to_takeoff_property(tmp_path):
    """Property-style integration: seeded random-ish pieces -> Nesting ->
    zero pairwise overlaps, everything on-sheet, and the nesting.json it
    emits prices cleanly through compute_takeoff with consistent math."""
    Nesting = pytest.importorskip("pipeline.Nesting")
    shapely_geom = pytest.importorskip("shapely.geometry")

    rng = random.Random(20260726)
    pieces = []
    for k in range(1, 8):
        w = rng.uniform(50.0, 400.0)
        h = rng.uniform(50.0, 300.0)
        cut = rng.uniform(0.1, 0.5)             # clipped corner -> pentagon
        ring = [[0.0, 0.0], [w, 0.0], [w, h * (1.0 - cut)],
                [w * (1.0 - cut), h], [0.0, h]]
        pieces.append({"id": f"piece-{k}", "name": f"p{k}",
                       "label": chr(ord("A") + k - 1),
                       "polygon": [[round(x, 3), round(y, 3)] for x, y in ring],
                       "holes": [], "cut_qty": rng.randint(1, 2)})

    gap_mm, width_in = 5.0, 54.0
    placements, used_len, total_area = Nesting.nest_pieces(
        pieces, width_in=width_in, gap_mm=gap_mm, rotations=[0.0, 90.0])
    assert len(placements) == sum(p["cut_qty"] for p in pieces)

    by_id = {p["id"]: p for p in pieces}
    polys = [Nesting.apply_placement(by_id[pl["piece_id"]]["polygon"], pl)
             for pl in placements]
    sheet_w_mm = width_in * 25.4
    for i, a in enumerate(polys):
        minx, miny, maxx, maxy = a.bounds
        assert minx >= -0.01 and miny >= -0.01
        assert maxx <= sheet_w_mm + 0.01 and maxy <= used_len + 0.01
        for b in polys[i + 1:]:
            assert a.intersection(b).area < 1e-6
            # placements rounded to 3 decimals -> small tolerance on the gap
            assert a.distance(b) >= gap_mm - 0.01

    doc = Nesting.nesting_doc("proptest", width_in, gap_mm, placements,
                              used_len, total_area)
    takeoff = Takeoff.compute_takeoff(doc, "canvas", MATERIALS_DOC)
    expected_yd = doc["used_length_in"] / 36.0 * 1.10
    # takeoff.json rounds yardage to 4 decimals (~0.1 mm) — match that here
    assert takeoff["linear_yd_per_unit"] == pytest.approx(expected_yd,
                                                          abs=5.1e-5)
    assert takeoff["material_cost_per_unit_usd"] == pytest.approx(
        round(takeoff["linear_yd_per_unit"] * 18.00, 2))
    assert 0.0 < takeoff["utilization"] <= 1.0
