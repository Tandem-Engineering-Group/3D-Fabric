"""Shared pytest fixtures for the 3D-Fabric pipeline tests.

Puts the repo root on sys.path so `from pipeline import ...` works when
pytest is run from the repo root (or anywhere else).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from pipeline import common  # noqa: E402


@pytest.fixture
def sample_pieces_doc() -> dict:
    """A 3dfabric.pieces/1 document with 4 pieces (mm, CCW exterior rings):

    - body_front: 400x300 rectangle
    - gusset:     500x120 rectangle, cut_qty=2 (two copies must be placed)
    - flap_L:     concave L-shape
    - pocket:     small trapezoid
    """
    pieces = [
        common.Piece(
            id="piece-1", name="body_front", label="A",
            polygon=[[0, 0], [400, 0], [400, 300], [0, 300]],
        ),
        common.Piece(
            id="piece-2", name="gusset", label="B",
            polygon=[[0, 0], [500, 0], [500, 120], [0, 120]],
            cut_qty=2,
        ),
        common.Piece(
            id="piece-3", name="flap_L", label="C",
            polygon=[[0, 0], [300, 0], [300, 80], [100, 80],
                     [100, 220], [0, 220]],
        ),
        common.Piece(
            id="piece-4", name="pocket", label="D",
            polygon=[[0, 0], [150, 0], [120, 100], [30, 100]],
        ),
    ]
    return common.pieces_doc("unittote", pieces, seam_allowance_mm=10.0)


@pytest.fixture
def write_tmp_doc(tmp_path):
    """Writer fixture: dump a JSON doc (or raw text) into a per-test tmp dir.

    Usage: path = write_tmp_doc(doc)                       # pieces.json
           path = write_tmp_doc(svg_text, name="in.svg")   # raw text file
    """
    def _write(doc, name: str = "pieces.json") -> Path:
        p = tmp_path / name
        if isinstance(doc, str):
            p.write_text(doc, encoding="utf-8")
        else:
            p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return p
    return _write
