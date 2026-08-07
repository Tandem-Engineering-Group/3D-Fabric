"""Color Me Art fabric wrap system — pattern pieces from the build sheet.

The three padded carry wraps (A: base/front skirt, B: left side curtain,
C: right side + roof valance) are rectangles with bound edges, so the
flatten step is authored directly from the vendor build sheet (sheet 12/14,
rev A 2026-08-02) instead of going through Blender:

  Wrap A  54 x 24 in unwrapped   + 2 storage pockets 12 x 8 in
  Wrap B  40 x 31 in unwrapped   + 1 accessory pocket 10 x 10 in
  Wrap C  60 x 31 in unwrapped   + 1 accessory pocket 10 x 10 in
  plus 3 padded handle wraps and the 12 x 8 in hardware pouch (2 panels).

Edges are bound with 1 in webbing, so main panels carry NO seam allowance;
pocket cuts include hem/turn allowances (25 mm top hem, 12 mm sides/bottom).

Writes three designs (outer / liner / foam) in the standard pipeline layout:
  patterns/<design>/pieces.json + <design>_pattern.svg

Usage: python scripts/make_wrap_patterns.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import common
from pipeline.common import Piece

IN = 25.4


def rect(w_mm, h_mm):
    return [[0.0, 0.0], [w_mm, 0.0], [w_mm, h_mm], [0.0, h_mm]]


def pocket_cut(w_in, h_in):
    """Finished pocket size + 25 mm top hem + 12 mm sides/bottom turn."""
    return rect(w_in * IN + 2 * 12, h_in * IN + 25 + 12)


MAINS = [
    ("wrapA_main", "A", 54, 24, "Wrap A — base/front skirt. Edges webbing-bound, no SA."),
    ("wrapB_main", "B", 40, 31, "Wrap B — left side curtain. Edges webbing-bound, no SA."),
    ("wrapC_main", "C", 60, 31, "Wrap C — right side + roof valance. Edges webbing-bound, no SA."),
]


def outer_pieces():
    pieces = []
    n = 1
    for name, label, w, h, note in MAINS:
        pieces.append(Piece(id=f"piece-{n}", name=name, label=label,
                            polygon=rect(w * IN, h * IN), notes=note))
        n += 1
    pieces.append(Piece(id=f"piece-{n}", name="wrapA_pocket", label="D",
                        polygon=pocket_cut(12, 8), cut_qty=2,
                        notes="Storage pockets 12x8 finished; hems included in cut."))
    n += 1
    pieces.append(Piece(id=f"piece-{n}", name="wrapBC_pocket", label="E",
                        polygon=pocket_cut(10, 10), cut_qty=2,
                        notes="Accessory pockets 10x10 finished (one wrap B, one wrap C)."))
    n += 1
    pieces.append(Piece(id=f"piece-{n}", name="handle_pad", label="F",
                        polygon=rect(8 * IN, 4.5 * IN), cut_qty=3,
                        notes="Padded handle wrap, folds over 1 in webbing carry handle."))
    n += 1
    pieces.append(Piece(id=f"piece-{n}", name="pouch_panel", label="G",
                        polygon=rect(12.5 * IN, 8.5 * IN), cut_qty=2,
                        notes="Hardware pouch front/back, 12x8 finished, #5 zipper top."))
    return pieces


def liner_pieces():
    pieces = []
    for i, (name, label, w, h, _) in enumerate(MAINS, start=1):
        pieces.append(Piece(id=f"piece-{i}", name=name.replace("_main", "_liner"),
                            label=label, polygon=rect(w * IN, h * IN),
                            notes="Tricot liner, quilted to foam, bound with outer."))
    pieces.append(Piece(id="piece-4", name="pouch_liner", label="G",
                        polygon=rect(12.5 * IN, 8.5 * IN), cut_qty=2))
    return pieces


def foam_pieces():
    return [Piece(id=f"piece-{i}", name=name.replace("_main", "_foam"),
                  label=label, polygon=rect(w * IN - 20, h * IN - 20),
                  notes="1/8 in closed-cell foam, trimmed 10 mm inside binding.")
            for i, (name, label, w, h, _) in enumerate(MAINS, start=1)]


def write_design(design, pieces):
    doc = common.pieces_doc(design, pieces, seam_allowance_mm=0.0,
                            source_mesh=None,
                            extra={"source": "colormeartbuildsheet.pdf sheet 12/14 rev A 2026-08-02",
                                   "note": "Edges webbing-bound; hems included in pocket cuts."})
    pdir = common.PATTERNS_DIR / design
    common.write_json(pdir / "pieces.json", doc)

    # labeled pattern sheet, pieces laid out in a simple row-wrap
    pad = 40.0
    x = y = pad
    row_h = 0.0
    placed = []
    sheet_w = 3300.0
    for p in doc["pieces"]:
        xs = [pt[0] for pt in p["polygon"]]
        ys = [pt[1] for pt in p["polygon"]]
        w, h = max(xs), max(ys)
        if x + w + pad > sheet_w:
            x = pad
            y += row_h + pad
            row_h = 0.0
        placed.append((p, x, y))
        x += w + pad
        row_h = max(row_h, h)
    total_h = y + row_h + pad
    svg = [common.svg_open(sheet_w, total_h, f"{design} pattern — {common.draft_header('pattern sheet')}")]
    for p, px, py in placed:
        svg.append(common.piece_group_svg(p, transform=f"translate({px:.1f},{py:.1f})"))
    svg.append("</svg>")
    (pdir / f"{design}_pattern.svg").write_text("\n".join(svg), encoding="utf-8")
    print(f"{design}: {len(pieces)} pieces -> {pdir}")


def main():
    write_design("color-me-art-wraps", outer_pieces())
    write_design("color-me-art-wraps-liner", liner_pieces())
    write_design("color-me-art-wraps-foam", foam_pieces())


if __name__ == "__main__":
    main()
