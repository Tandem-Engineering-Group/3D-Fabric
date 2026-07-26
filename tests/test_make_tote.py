"""Smoke tests for scripts/make_tote.py.

test_script_compiles_and_help always runs (py_compile + CLI --help via plain
Python — the script must not need bpy just to import/parse args).
test_tote_end_to_end drives Blender headless via common.run_blender and is
skipped while Blender is absent.
Run from repo root:
  python -m pytest "tests/test_make_tote.py" -q
"""

import json
import py_compile
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
import trimesh

from pipeline import common

SCRIPT = REPO_ROOT / "scripts" / "make_tote.py"


def test_script_compiles_and_help(tmp_path):
    py_compile.compile(str(SCRIPT), cfile=str(tmp_path / "make_tote.pyc"),
                       doraise=True)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    for flag in ("--width-mm", "--height-mm", "--depth-mm",
                 "--strap-length-mm", "--strap-width-mm", "--quad-mm",
                 "--out", "--render", "--json-report"):
        assert flag in proc.stdout


@pytest.mark.skipif(not common.blender_available(),
                    reason="Blender not installed (yet)")
def test_tote_end_to_end(tmp_path):
    out = tmp_path / "designs" / "FeltCheckTote.glb"
    png = tmp_path / "designs" / "FeltCheckTote.png"
    report_path = tmp_path / "designs" / "FeltCheckTote_report.json"

    common.run_blender(SCRIPT, [
        "--width-mm", "350", "--height-mm", "320", "--depth-mm", "120",
        "--strap-length-mm", "550", "--strap-width-mm", "30",
        "--quad-mm", "20",
        "--out", str(out), "--render", str(png),
        "--json-report", str(report_path),
    ], log_name="test_make_tote.log")

    # GLB: loads in trimesh with body + two straps worth of geometry
    assert out.is_file()
    loaded = trimesh.load(str(out))
    geoms = (list(loaded.geometry.values())
             if isinstance(loaded, trimesh.Scene) else [loaded])
    assert len(geoms) >= 3, f"expected >=3 geometries, got {len(geoms)}"
    total_verts = sum(len(g.vertices) for g in geoms)
    # 5 body panels at ~20 mm quads alone are hundreds of vertices
    assert total_verts >= 300, f"too few vertices: {total_verts}"

    # Render: a real image, not a stub
    assert png.is_file()
    assert png.stat().st_size > 10_000, f"PNG too small: {png.stat().st_size}"

    # Verification report
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["objects"] >= 3
    assert report["seam_edges"] > 0
    assert report["tris"] > 0
