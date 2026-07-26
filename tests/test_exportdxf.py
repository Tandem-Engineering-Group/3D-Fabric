"""ExportDXF round-trip tests against the committed FeltCheckTote artifacts."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PIECES = REPO / "patterns/FeltCheckTote/pieces.json"
NESTING = REPO / "takeoffs/FeltCheckTote/nesting.json"


@pytest.mark.skipif(not PIECES.is_file(), reason="tote artifacts not built")
def test_pattern_dxf_roundtrip(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    out = tmp_path / "pattern.dxf"
    r = subprocess.run([sys.executable, str(REPO / "pipeline/ExportDXF.py"),
                        "--pieces", str(PIECES), "--out", str(out)],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    cuts = [e for e in msp if e.dxf.layer == "CUT"]
    stitches = [e for e in msp if e.dxf.layer == "STITCH"]
    labels = [e for e in msp if e.dxf.layer == "LABEL"]
    assert len(cuts) == 7 and len(stitches) == 7 and len(labels) == 7
    assert doc.header["$INSUNITS"] == 4
    auditor = doc.audit()
    assert not auditor.has_errors


@pytest.mark.skipif(not (PIECES.is_file() and NESTING.is_file()),
                    reason="tote artifacts not built")
def test_nested_dxf_roundtrip(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    out = tmp_path / "nested.dxf"
    r = subprocess.run([sys.executable, str(REPO / "pipeline/ExportDXF.py"),
                        "--pieces", str(PIECES), "--nesting", str(NESTING),
                        "--out", str(out)],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    cuts = [e for e in msp if e.dxf.layer == "CUT"]
    assert len(cuts) == 7  # one per placement
    # everything inside the 54in sheet width
    for e in cuts:
        xs = [p[0] for p in e.get_points("xy")]
        assert min(xs) >= -0.5 and max(xs) <= 54 * 25.4 + 0.5
    assert not doc.audit().has_errors
