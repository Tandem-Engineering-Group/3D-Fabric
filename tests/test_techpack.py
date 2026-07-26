"""Smoke tests for pipeline/TechPack.py — synthetic fixtures, no Blender."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import TechPack, common  # noqa: E402


def rect(w, h, x0=0.0, y0=0.0):
    """CCW rectangle ring, first point not repeated."""
    return [[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]]


def pieces_fixture():
    pieces = [
        common.Piece(id="piece-1", name="body_front", label="A",
                     polygon=rect(300, 200), cut_qty=2),
        common.Piece(id="piece-2", name="gusset", label="B",
                     polygon=rect(100, 50), cut_qty=1),
    ]
    return common.pieces_doc("testbag", pieces, seam_allowance_mm=10.0,
                             source_mesh="designs/testbag.glb")


def takeoff_fixture(**overrides):
    doc = {
        "schema": "3dfabric.takeoff/1",
        "design": "testbag",
        "material": "canvas",
        "material_display": "Test canvas 12oz",
        "unit": "yard",
        "qty": 1,
        "sheet_width_in": 54.0,
        "utilization": 0.55,
        "linear_yd_per_unit": 1.1,
        "material_cost_per_unit_usd": 19.80,
        "waste_factor": 0.10,
        "assumptions": ["test assumption"],
        "draft": common.draft_header("takeoff"),
    }
    doc.update(overrides)
    return doc


def test_md_sections_and_math():
    md = TechPack.build_techpack_md(pieces_fixture(), takeoff_fixture())

    assert md.startswith("# Tech Pack — testbag")
    assert "> **DRAFT" in md                       # DRAFT banner blockquote

    # Overview: overall bbox 300 x 200 mm = 11.81 x 7.87 in
    assert "300 × 200 mm" in md
    assert "11.81 × 7.87 in" in md
    assert "designs/testbag.glb" in md

    # Piece table rows: label, name, qty, dims, area
    assert "| A | body_front | 2 | 300 × 200 | 600.0 |" in md
    assert "| B | gusset | 1 | 100 × 50 | 50.0 |" in md

    # Materials & takeoff
    assert "Test canvas 12oz" in md
    assert "55.0%" in md
    assert "1.100 yd" in md
    assert "$19.80" in md
    assert "test assumption" in md

    # Hardware BOM stub
    for item in ("Zipper", "Rivets", "D-rings", "Magnetic snap"):
        assert item in md

    # Construction notes numbered stub
    for i in range(1, 6):
        assert f"\n{i}. " in md

    # Seam allowance note
    assert "## Seam allowance" in md
    assert "10 mm seam allowance" in md


def test_hide_takeoff_renders_hides_row():
    takeoff = takeoff_fixture(unit="hide", hides_per_unit=2,
                              material_cost_per_unit_usd=320.0)
    del takeoff["linear_yd_per_unit"]
    md = TechPack.build_techpack_md(pieces_fixture(), takeoff)
    assert "| Hides per unit | 2 |" in md
    assert "Linear yd per unit" not in md
    assert "$320.00" in md


def test_mesh_stats_included():
    stats = {"verts": 1234, "faces": 2400, "source": "testbag.glb"}
    md = TechPack.build_techpack_md(pieces_fixture(), takeoff_fixture(),
                                    mesh_stats=stats)
    assert "### Mesh stats" in md
    assert "1234" in md and "2400" in md


def test_piece_area_subtracts_holes():
    piece = {"polygon": rect(100, 100), "holes": [rect(10, 10, 20, 20)]}
    assert TechPack.piece_area_cm2(piece) == 99.0


def test_cli_end_to_end(tmp_path):
    pieces_path = tmp_path / "pieces.json"
    pieces_path.write_text(json.dumps(pieces_fixture()), encoding="utf-8")
    takeoff_path = tmp_path / "takeoff.json"
    takeoff_path.write_text(json.dumps(takeoff_fixture()), encoding="utf-8")
    stats_path = tmp_path / "meshstats.json"
    stats_path.write_text(json.dumps({"verts": 777}), encoding="utf-8")
    out_dir = tmp_path / "techpack"

    rc = TechPack.main([
        "--pieces", str(pieces_path),
        "--takeoff", str(takeoff_path),
        "--mesh-stats", str(stats_path),
        "--out-dir", str(out_dir),
    ])
    assert rc == 0

    out_path = out_dir / "testbag.md"
    assert out_path.is_file()
    md = out_path.read_text(encoding="utf-8")
    assert "> **DRAFT" in md
    assert "body_front" in md
    assert "777" in md
