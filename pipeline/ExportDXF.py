"""ExportDXF — pattern pieces -> AutoCAD/laser-cutter DXF (millimeters).

  python pipeline/ExportDXF.py --pieces "patterns/X/pieces.json" --out "patterns/X/X_pattern.dxf"
  python pipeline/ExportDXF.py --pieces ... --nesting "takeoffs/X/nesting.json" --out "takeoffs/X/X_cutpaths.dxf"

Without --nesting, pieces are laid out in non-overlapping rows (a pattern
sheet). With --nesting, pieces sit at their nested cut positions — the file a
laser bed actually runs. Layers: CUT (continuous, color 7), STITCH (dashed,
red), LABEL (text, green). Y axis is flipped from the SVG convention so the
DXF displays with the same visual orientation in AutoCAD.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import common  # noqa: E402


def _new_doc():
    doc = ezdxf.new("R2010", setup=True)  # setup=True defines DASHED linetype
    doc.header["$INSUNITS"] = 4           # millimeters
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add("CUT", color=7)
    doc.layers.add("STITCH", color=1, linetype="DASHED")
    doc.layers.add("LABEL", color=3)
    return doc


def _flip(ring, height):
    return [(x, height - y) for x, y in ring]


def _add_piece(msp, piece, dx, dy, height, rings_cut, rings_stitch):
    """rings are piece-local; dx/dy translate, then y flips against height."""
    for ring in rings_cut:
        msp.add_lwpolyline(_flip([(x + dx, y + dy) for x, y in ring], height),
                           close=True, dxfattribs={"layer": "CUT"})
    for ring in rings_stitch:
        msp.add_lwpolyline(_flip([(x + dx, y + dy) for x, y in ring], height),
                           close=True, dxfattribs={"layer": "STITCH"})
    xs = [p[0] for p in rings_cut[0]]
    ys = [p[1] for p in rings_cut[0]]
    cx, cy = (min(xs) + max(xs)) / 2 + dx, (min(ys) + max(ys)) / 2 + dy
    label = f"{piece.get('label', '?')} {piece.get('name', '')}".strip()
    msp.add_text(label, height=10,
                 dxfattribs={"layer": "LABEL"}).set_placement(
        (cx, height - cy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def export_pattern(pieces_doc: dict, out: Path, margin: float = 20.0,
                   max_row: float = 1200.0) -> int:
    doc = _new_doc()
    msp = doc.modelspace()
    # same row layout as the SVG pattern sheet
    placed, x, y, row_h, sheet_h = [], margin, margin, 0.0, 0.0
    for p in pieces_doc["pieces"]:
        minx, miny, maxx, maxy = common.bbox_of(p["polygon"])
        w, h = maxx - minx, maxy - miny
        if x + w + margin > max_row and placed:
            x, y, row_h = margin, y + row_h + margin, 0.0
        placed.append((p, x, y))
        x += w + margin
        row_h = max(row_h, h)
    sheet_h = y + row_h + margin
    for p, px, py in placed:
        cut = [p["polygon"]] + list(p.get("holes", []))
        stitch = [p["stitch_polygon"]] if p.get("stitch_polygon") else []
        _add_piece(msp, p, px, py, sheet_h, cut, stitch)
    doc.saveas(out)
    return len(placed)


def export_nested(pieces_doc: dict, nesting: dict, out: Path) -> int:
    from pipeline import Nesting
    by_id = {p["id"]: p for p in pieces_doc["pieces"]}
    doc = _new_doc()
    msp = doc.modelspace()
    height = float(nesting["used_length_mm"])
    sheet_w = float(nesting["sheet_width_in"]) * common.MM_PER_IN
    msp.add_lwpolyline(_flip([(0, 0), (sheet_w, 0), (sheet_w, height), (0, height)],
                             height), close=True, dxfattribs={"layer": "LABEL"})
    n = 0
    for pl in nesting["placements"]:
        p = by_id[pl["piece_id"]]

        def placed_ring(ring):
            poly = Nesting.apply_placement(ring, pl)
            return list(poly.exterior.coords)[:-1]

        cut = [placed_ring(p["polygon"])] + [placed_ring(h)
                                             for h in p.get("holes", [])]
        stitch = ([placed_ring(p["stitch_polygon"])]
                  if p.get("stitch_polygon") else [])
        _add_piece(msp, p, 0.0, 0.0, height, cut, stitch)
        n += 1
    doc.saveas(out)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pieces", required=True, help="pieces.json")
    ap.add_argument("--nesting", help="nesting.json -> nested cut layout mode")
    ap.add_argument("--out", required=True, help="output .dxf path")
    args = ap.parse_args()

    pieces_doc = common.load_pieces(args.pieces)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.nesting:
        import json
        nesting = json.loads(Path(args.nesting).read_text(encoding="utf-8"))
        n = export_nested(pieces_doc, nesting, out)
        print(f"{n} nested placements -> {out}")
    else:
        n = export_pattern(pieces_doc, out)
        print(f"{n} pieces (pattern sheet) -> {out}")
    print(common.draft_header("DXF cut paths"))


if __name__ == "__main__":
    main()
