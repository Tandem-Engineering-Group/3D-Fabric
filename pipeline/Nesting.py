"""Nest pattern pieces onto a fabric sheet (bottom-left-fill greedy).

CLI:
    python pipeline/Nesting.py --pieces patterns/<design>/pieces.json
    python pipeline/Nesting.py --svg patterns/<design>/<design>_pattern.svg --design <design>

Options:
    --width-in FLOAT   fabric sheet width in inches (default 54)
    --gap-mm FLOAT     minimum gap between cut lines in mm (default 5)
    --rotations CSV    allowed rotations in degrees (default "0,90,180,270")
    --out-dir PATH     output directory (default takeoffs/<design>)
    --design NAME      design name (required with --svg, optional override
                       with --pieces)

Outputs (1 SVG user unit = 1 mm, y-down):
    <out-dir>/nesting.json          3dfabric.nesting/1 document
    <out-dir>/nested_<W>in.svg      sheet outline + placed pieces

Placement convention: the placed cut line equals the piece polygon rotated by
rotation_deg about the origin (0,0), then translated by (x_mm, y_mm) -- i.e.
exactly the SVG transform 'translate(x_mm y_mm) rotate(rotation_deg)'.
apply_placement() reproduces a placed polygon from a placement record.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import common  # noqa: E402

NESTING_SCHEMA = "3dfabric.nesting/1"
DEFAULT_GAP_MM = 5.0
DEFAULT_ROTATIONS = "0,90,180,270"

# Pieces are padded by gap/2 minus this epsilon so that two pieces separated
# by exactly gap_mm (the bbox-corner candidates land there) do not register
# as touching/intersecting in GEOS.
_EPS = 1e-6


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _clean_polygon(ring: list) -> Polygon:
    """Exterior-ring shapely polygon, repaired if self-touching/invalid."""
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
    if poly.is_empty or poly.area <= 0:
        raise ValueError("degenerate polygon (zero area)")
    return poly


def load_pieces_from_svg(svg_path: str | Path, sample_mm: float = 1.0,
                         min_area_mm2: float = 1.0) -> list[dict]:
    """Extract piece dicts from an SVG (1 unit = 1 mm).

    Parses <path> elements plus <polygon>/<polyline>/<rect>/... (svgpathtools
    converts those to paths), sampling curved segments to ~sample_mm
    polylines.  Rings fully contained in a larger ring (stitch lines, hole
    outlines) are dropped so only outermost cut lines become pieces.
    Element transforms are NOT applied -- feed flat pattern-sheet SVGs.
    """
    from svgpathtools import svg2paths

    paths, _attrs = svg2paths(str(svg_path))
    polys: list[Polygon] = []
    for path in paths:
        if len(path) == 0:
            continue
        ring: list[tuple[float, float]] = []
        for seg in path:
            try:
                seg_len = seg.length()
            except Exception:
                seg_len = abs(seg.end - seg.start)
            n = max(1, math.ceil(seg_len / max(sample_mm, 1e-3)))
            for i in range(n):
                z = seg.point(i / n)
                pt = (float(z.real), float(z.imag))
                if not ring or math.dist(ring[-1], pt) > 1e-6:
                    ring.append(pt)
        if len(ring) >= 2 and math.dist(ring[0], ring[-1]) <= 1e-6:
            ring.pop()
        if len(ring) < 3:
            continue
        try:
            poly = _clean_polygon(ring)
        except ValueError:
            continue
        if poly.area >= min_area_mm2:
            polys.append(poly)

    pieces: list[dict] = []
    k = 0
    for i, p in enumerate(polys):
        nested_inside = any(
            j != i and q.area > p.area + 1e-9 and q.contains(p)
            for j, q in enumerate(polys))
        if nested_inside:
            continue
        k += 1
        ext = orient(p, sign=1.0).exterior.coords
        pieces.append({
            "id": f"piece-{k}",
            "name": f"svg-shape-{k}",
            "label": chr(ord("A") + (k - 1) % 26),
            "polygon": [[round(x, 3), round(y, 3)] for x, y in list(ext)[:-1]],
            "holes": [],
            "cut_qty": 1,
        })
    return pieces


# ---------------------------------------------------------------------------
# Nesting core
# ---------------------------------------------------------------------------

def parse_rotations(spec: str) -> list[float]:
    out: list[float] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        deg = float(tok) % 360.0
        if deg not in out:
            out.append(deg)
    if not out:
        raise ValueError(f"no rotations parsed from {spec!r}")
    return out


def apply_placement(polygon: list, placement: dict) -> Polygon:
    """Rebuild the placed cut-line polygon from a placement record."""
    poly = Polygon(polygon)
    if placement["rotation_deg"]:
        poly = affinity.rotate(poly, placement["rotation_deg"], origin=(0, 0))
    return affinity.translate(poly, placement["x_mm"], placement["y_mm"])


def _variants(shell: Polygon, rotations: list[float], pad: float) -> list[dict]:
    """Per-rotation: bbox-normalized polygon + its padded twin, precomputed."""
    out = []
    for deg in rotations:
        r = affinity.rotate(shell, deg, origin=(0, 0)) if deg else shell
        minx, miny, maxx, maxy = r.bounds
        norm = affinity.translate(r, -minx, -miny)
        out.append({
            "deg": deg,
            "w": maxx - minx,
            "h": maxy - miny,
            "rminx": minx,
            "rminy": miny,
            "norm": norm,
            "norm_pad": norm.buffer(pad) if pad > 0 else norm,
        })
    return out


def _first_fit(v: dict, xs: list[float], ys: list[float], sheet_w: float,
               tree: STRtree | None, best: tuple | None):
    """Lowest (y, x) candidate where this variant fits without overlap.

    Candidates are scanned in (y, x) lexicographic order, pruned against the
    best position already found for an earlier rotation.
    """
    for y in ys:
        if best is not None and y > best[0] + 1e-9:
            break
        for x in xs:
            if best is not None and abs(y - best[0]) <= 1e-9 and x >= best[1] - 1e-9:
                break
            if x + v["w"] > sheet_w + 1e-6:
                break  # xs sorted ascending: nothing further fits
            cand_pad = affinity.translate(v["norm_pad"], x, y)
            if tree is None or len(tree.query(cand_pad, predicate="intersects")) == 0:
                return (y, x)
    return None


def nest_pieces(pieces: list[dict], width_in: float = common.DEFAULT_SHEET_WIDTH_IN,
                gap_mm: float = DEFAULT_GAP_MM,
                rotations: list[float] | tuple = (0.0, 90.0, 180.0, 270.0),
                ) -> tuple[list[dict], float, float]:
    """Bottom-left-fill greedy nesting.

    Returns (placements, used_length_mm, total_piece_area_mm2).  Piece area
    counts the exterior ring only: interior holes still consume fabric.
    """
    if not pieces:
        raise ValueError("no pieces to nest")
    sheet_w = width_in * common.MM_PER_IN
    pad = max(gap_mm / 2.0 - _EPS, 0.0)

    prepped = []
    for p in pieces:
        shell = _clean_polygon(p["polygon"])
        qty = max(int(p.get("cut_qty") or 1), 1)
        prepped.append((p, shell, shell.area, qty))
    prepped.sort(key=lambda t: -t[2])

    variant_cache: dict[str, list[dict]] = {}
    placed: list[Polygon] = []
    placed_pad: list[Polygon] = []
    placements: list[dict] = []
    tree: STRtree | None = None
    # Candidate positions: origin plus right-of / above-of every placed bbox.
    cand_xs = {0.0}
    cand_ys = {0.0}

    for p, shell, _area, qty in prepped:
        pid = p["id"]
        if pid not in variant_cache:
            variant_cache[pid] = _variants(shell, list(rotations), pad)
        variants = variant_cache[pid]
        if all(v["w"] > sheet_w + 1e-6 for v in variants):
            raise ValueError(
                f"{pid}: piece exceeds sheet width {width_in} in at every rotation")

        for copy_i in range(1, qty + 1):
            xs = sorted(cand_xs)
            ys = sorted(cand_ys)
            # Score across rotations by how far the piece TOP would extend the
            # marker (y + h), not just bottom-left (y, x) — otherwise a long
            # strap stands upright at (0,0) and pins the whole sheet length
            # when lying flat costs nothing.
            best = None  # (top_y, y, x, variant)
            for v in variants:
                if v["w"] > sheet_w + 1e-6:
                    continue
                hit = _first_fit(v, xs, ys, sheet_w, tree, None)
                if hit is not None:
                    score = (hit[0] + v["h"], hit[0], hit[1])
                    if best is None or score < best[:3]:
                        best = (*score, v)
            if best is None:  # unreachable: top-of-sheet candidate always fits
                raise RuntimeError(f"{pid}: no valid position found")
            _top, y, x, v = best
            poly = affinity.translate(v["norm"], x, y)
            placed.append(poly)
            placed_pad.append(affinity.translate(v["norm_pad"], x, y))
            tree = STRtree(placed_pad)
            _bx0, _by0, bx1, by1 = poly.bounds
            cand_xs.add(bx1 + gap_mm)
            cand_ys.add(by1 + gap_mm)
            placements.append({
                "piece_id": pid,
                "copy": copy_i,
                "x_mm": round(x - v["rminx"], 3),
                "y_mm": round(y - v["rminy"], 3),
                "rotation_deg": v["deg"],
            })

    used_len = max(g.bounds[3] for g in placed)
    total_area = sum(a * q for _p, _s, a, q in prepped)
    return placements, used_len, total_area


def nesting_doc(design: str, width_in: float, gap_mm: float,
                placements: list[dict], used_length_mm: float,
                total_piece_area_mm2: float) -> dict:
    used_in = common.mm_to_in(used_length_mm)
    sheet_area = width_in * common.MM_PER_IN * used_length_mm
    return {
        "schema": NESTING_SCHEMA,
        "design": design,
        "sheet_width_in": width_in,
        "gap_mm": gap_mm,
        "used_length_mm": round(used_length_mm, 2),
        "used_length_in": round(used_in, 2),
        "used_length_yd": round(common.in_to_yd(used_in), 3),
        "utilization": round(total_piece_area_mm2 / sheet_area, 8) if sheet_area > 0 else 0.0,
        "total_piece_area_mm2": round(total_piece_area_mm2, 1),
        "draft": common.draft_header("nesting layout"),
        "placements": placements,
    }


# ---------------------------------------------------------------------------
# SVG output
# ---------------------------------------------------------------------------

def nested_svg(design: str, width_in: float, used_length_mm: float,
               placements: list[dict], pieces_by_id: dict[str, dict]) -> str:
    sheet_w = width_in * common.MM_PER_IN
    h = max(used_length_mm, 1.0)
    parts = [common.svg_open(sheet_w, h, f"{design} nested @ {width_in:g} in")]
    parts.append(f'<rect x="0" y="0" width="{sheet_w:.3f}" height="{h:.3f}" '
                 f'fill="none" stroke="#0a84ff" stroke-width="1" '
                 f'stroke-dasharray="8 4"/>')
    for pl in placements:
        src = pieces_by_id[pl["piece_id"]]
        piece = dict(src)
        piece["id"] = f'{src["id"]}-c{pl["copy"]}'
        tr = (f'translate({pl["x_mm"]:.3f} {pl["y_mm"]:.3f}) '
              f'rotate({pl["rotation_deg"]:g})')
        parts.append(common.piece_group_svg(piece, transform=tr))
    parts.append("</svg>\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run(pieces: list[dict], design: str, width_in: float, gap_mm: float,
        rotations: list[float], out_dir: Path) -> dict:
    placements, used_len, total_area = nest_pieces(
        pieces, width_in=width_in, gap_mm=gap_mm, rotations=rotations)
    doc = nesting_doc(design, width_in, gap_mm, placements, used_len, total_area)
    common.write_json(out_dir / "nesting.json", doc)
    svg_text = nested_svg(design, width_in, used_len, placements,
                          {p["id"]: p for p in pieces})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"nested_{width_in:g}in.svg").write_text(svg_text, encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="Nesting",
        description="Nest pattern pieces onto a fabric sheet "
                    "(bottom-left-fill greedy, mm units).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pieces", help="pieces.json (3dfabric.pieces/1)")
    src.add_argument("--svg", help="pattern SVG to parse pieces from (1 unit = 1 mm)")
    ap.add_argument("--width-in", type=float, default=common.DEFAULT_SHEET_WIDTH_IN,
                    help="sheet width in inches (default %(default)s)")
    ap.add_argument("--gap-mm", type=float, default=DEFAULT_GAP_MM,
                    help="minimum gap between pieces in mm (default %(default)s)")
    ap.add_argument("--rotations", default=DEFAULT_ROTATIONS,
                    help="comma-separated rotation angles in degrees "
                         "(default %(default)s)")
    ap.add_argument("--out-dir", default=None,
                    help="output directory (default takeoffs/<design>)")
    ap.add_argument("--design", default=None,
                    help="design name (required with --svg)")
    args = ap.parse_args(argv)

    if args.svg:
        if not args.design:
            ap.error("--design is required with --svg")
        design = args.design
        pieces = load_pieces_from_svg(args.svg)
        if not pieces:
            ap.error(f"no usable closed shapes found in {args.svg}")
    else:
        doc = common.load_pieces(args.pieces)
        design = args.design or doc.get("design") or "design"
        pieces = doc["pieces"]

    try:
        rotations = parse_rotations(args.rotations)
    except ValueError as e:
        ap.error(str(e))

    out_dir = Path(args.out_dir) if args.out_dir else common.TAKEOFFS_DIR / design
    result = run(pieces, design, args.width_in, args.gap_mm, rotations, out_dir)

    print(f"nested {len(result['placements'])} placements for '{design}' "
          f"on {args.width_in:g} in sheet")
    print(f"  used length: {result['used_length_mm']} mm "
          f"({result['used_length_yd']} yd), "
          f"utilization {result['utilization']:.1%}")
    print(f"  wrote {out_dir / 'nesting.json'}")
    print(f"  wrote {out_dir / f'nested_{args.width_in:g}in.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
