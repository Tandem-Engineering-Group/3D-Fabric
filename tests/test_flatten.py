"""Tests for pipeline/SeamsAndFlatten.py — synthetic post-process always; full
Blender+addon run only when both are available."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline import common  # noqa: E402
from pipeline.SeamsAndFlatten import (  # noqa: E402
    build_pieces, parse_raw_svg, pattern_sheet_svg)

VENV_PY = sys.executable

# Mimics the addon's output: viewBox in mm, <g><path class="seam">, second piece
# has a hole as a second M-subpath, plus marker/text noise the parser must skip.
RAW_SVG = """<svg xmlns="http://www.w3.org/2000/svg"
 viewBox="0 0 1000 1000" width="1000mm" height="1000mm">
<defs><style>.seam{stroke: #000; stroke-width:1px; fill:white} .sewinguide{stroke-width:1px;}</style></defs>
<g><path class="seam" d="M 100,100 300,100 300,250 100,250 100,100 "/>
<text x="200" y="175" font-size="30">A</text>
<path class="sewinguide" d="M 100,100 105,95" stroke="#ff0000"/></g>
<g><path class="seam" d="M 400,100 700,100 700,400 400,400 400,100 M 500,200 600,200 600,300 500,300 500,200 "/></g>
</svg>"""


def test_parse_raw_svg_pieces_and_holes():
    polys = parse_raw_svg(RAW_SVG)
    assert len(polys) == 2
    with_hole = max(polys, key=lambda p: p.area)
    assert len(with_hole.interiors) == 1
    # 300x300 outer minus 100x100 hole
    assert with_hole.area == pytest.approx(300 * 300 - 100 * 100)


def test_build_pieces_cut_contains_stitch():
    pieces = build_pieces(parse_raw_svg(RAW_SVG), allowance_mm=10.0)
    assert [p.label for p in pieces] == ["A", "B"]  # area-desc labeling
    for p in pieces:
        from shapely.geometry import Polygon
        cut = Polygon(p.polygon)
        stitch = Polygon(p.stitch_polygon)
        assert cut.contains(stitch)
        # allowance grows the piece ~allowance on every side
        assert cut.bounds[2] - stitch.bounds[2] == pytest.approx(10.0, abs=0.5)
        minx, miny, *_ = cut.bounds
        assert (minx, miny) == (0.0, 0.0)  # origin-normalized
    # hole shrinks by allowance: 100 - 2*10 = 80 wide
    big = pieces[0]
    assert len(big.holes) == 1
    hx = [pt[0] for pt in big.holes[0]]
    assert max(hx) - min(hx) == pytest.approx(80.0, abs=0.5)


def test_cli_raw_svg_end_to_end(tmp_path):
    raw = tmp_path / "raw_1.svg"
    raw.write_text(RAW_SVG, encoding="utf-8")
    out = tmp_path / "out"
    r = subprocess.run([VENV_PY, str(REPO / "pipeline" / "SeamsAndFlatten.py"),
                        "--raw-svg", str(raw), "--design", "TestDesign",
                        "--out-dir", str(out)],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    doc = json.loads((out / "pieces.json").read_text())
    assert doc["schema"] == "3dfabric.pieces/1"
    assert len(doc["pieces"]) == 2
    assert "DRAFT" in doc["draft"]
    import svgpathtools
    paths, _ = svgpathtools.svg2paths(str(out / "TestDesign_pattern.svg"))
    assert len(paths) >= 2


def _addon_installed() -> bool:
    result = common.LOGS_DIR / "install_addons.result.json"
    if not result.is_file():
        return False
    return "seams_to_sewing_pattern" in json.loads(result.read_text())["enabled"]


@pytest.mark.skipif(not common.blender_available(), reason="Blender not installed")
@pytest.mark.skipif(not _addon_installed(), reason="seams addon not installed")
def test_full_blender_flatten(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    box = trimesh.creation.box(extents=[0.3, 0.3, 0.1])
    mesh_path = tmp_path / "box.glb"
    box.export(str(mesh_path))
    out = tmp_path / "out"
    r = subprocess.run([VENV_PY, str(REPO / "pipeline" / "SeamsAndFlatten.py"),
                        "--mesh", str(mesh_path), "--design", "BoxTest",
                        "--target-tris", "800", "--out-dir", str(out)],
                       capture_output=True, text=True, cwd=str(REPO),
                       timeout=900)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    doc = json.loads((out / "pieces.json").read_text())
    assert len(doc["pieces"]) >= 1
    for p in doc["pieces"]:
        assert len(p["polygon"]) >= 3
    assert (out / "BoxTest_pattern.svg").is_file()
