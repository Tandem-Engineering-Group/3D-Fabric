"""SeamsAndFlatten — mesh -> flattened, labeled sewing-pattern pieces.

  python pipeline/SeamsAndFlatten.py --mesh "designs/Tote.glb" --design Tote
  python pipeline/SeamsAndFlatten.py --raw-svg raw_1.svg --design Tote   # skip Blender

Stage 1 (Blender headless, scripts/blender_flatten.py): unfold each mesh object along
its seams with the Seams-to-Sewing-Pattern add-on, exporting raw SVGs (1 unit = 1 mm,
one <g><path class="seam"> per piece, M-subpaths = boundary + holes).
Stage 2 (pure Python): parse raw SVGs, fix rings with shapely, treat the raw outline as
the STITCH line, grow by --allowance-mm for the CUT line (holes shrink accordingly),
label pieces A.. by area desc, then write patterns/<design>/pieces.json and a laid-out
<design>_pattern.svg.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import common  # noqa: E402

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _rings_from_path_d(d: str) -> list[list[list[float]]]:
    """Split a path 'd' into rings. Handles the addon's 'M x,y x,y ...' form plus
    absolute L/Z; curves are not expected in raw pattern SVGs."""
    rings = []
    for sub in re.split(r"[Mm]", d):
        nums = [float(n) for n in _NUM.findall(sub)]
        pts = [[nums[i], nums[i + 1]] for i in range(0, len(nums) - 1, 2)]
        if len(pts) >= 3:
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                rings.append(pts)
    return rings


def _clean(ring: list) -> Polygon | None:
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return None
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def parse_raw_svg(svg_text: str, min_area_mm2: float = 100.0) -> list[Polygon]:
    """Extract piece polygons (with holes) from a raw addon SVG. Returns shapely
    Polygons in mm; one per piece."""
    root = ET.fromstring(svg_text)
    paths = [el for el in root.iter() if el.tag.split("}")[-1] == "path"]
    seam_paths = [p for p in paths if "seam" in (p.get("class") or "")]
    if seam_paths:
        paths = seam_paths
    pieces: list[Polygon] = []
    for p in paths:
        rings = [r for r in (_clean(r) for r in _rings_from_path_d(p.get("d", "")))
                 if r is not None and r.area >= min_area_mm2]
        if not rings:
            continue
        rings.sort(key=lambda r: -r.area)
        # Within one path: biggest ring is the boundary; contained rings are
        # holes; stray uncontained rings become their own piece (defensive).
        outer, holes, extras = rings[0], [], []
        for r in rings[1:]:
            (holes if outer.contains(r.representative_point()) else extras).append(r)
        pieces.append(Polygon(outer.exterior.coords,
                              [h.exterior.coords for h in holes]))
        pieces.extend(Polygon(e.exterior.coords) for e in extras)
    return pieces


def build_pieces(polys: list[Polygon], allowance_mm: float) -> list[common.Piece]:
    """Stitch polygon -> cut polygon (buffer +allowance; holes shrink), origin-
    normalized, labeled A.. by area desc."""
    order = sorted(range(len(polys)), key=lambda i: -polys[i].area)
    pieces = []
    for rank, idx in enumerate(order):
        stitch = orient(polys[idx], sign=1.0)
        cut = stitch.buffer(allowance_mm, join_style=1, quad_segs=16)
        if cut.geom_type == "MultiPolygon":
            cut = max(cut.geoms, key=lambda g: g.area)
        minx, miny, *_ = cut.bounds

        def ring(coords):
            return [[round(x - minx, 3), round(y - miny, 3)] for x, y in coords[:-1]]

        label = ""
        n = rank
        while True:
            label = chr(ord("A") + n % 26) + label
            n = n // 26 - 1
            if n < 0:
                break
        pieces.append(common.Piece(
            id=f"piece-{rank + 1}",
            name=f"piece-{rank + 1}",
            label=label,
            polygon=ring(list(cut.exterior.coords)),
            holes=[ring(list(h.coords)) for h in cut.interiors],
            stitch_polygon=ring(list(stitch.exterior.coords)),
            cut_qty=1,
        ))
    return pieces


def pattern_sheet_svg(pieces: list[common.Piece], design: str,
                      margin_mm: float = 20.0, max_row_mm: float = 1200.0) -> str:
    """Human-readable pattern sheet: pieces in non-overlapping rows with labels."""
    x, y, row_h = margin_mm, margin_mm, 0.0
    placed, sheet_w = [], 0.0
    for p in pieces:
        minx, miny, maxx, maxy = common.bbox_of(p.polygon)
        w, h = maxx - minx, maxy - miny
        if x + w + margin_mm > max_row_mm and placed:
            x, y, row_h = margin_mm, y + row_h + margin_mm, 0.0
        placed.append((p, x, y))
        x += w + margin_mm
        row_h = max(row_h, h)
        sheet_w = max(sheet_w, x)
    sheet_h = y + row_h + margin_mm
    out = [common.svg_open(sheet_w, sheet_h, f"{design} — pattern pieces")]
    for p, px, py in placed:
        out.append(common.piece_group_svg(p.to_dict(),
                                          transform=f"translate({px:.1f} {py:.1f})"))
    out.append("</svg>")
    return "\n".join(out)


def run_blender_stage(mesh: Path, out_dir: Path, design: str, unwrap: str,
                      target_tris: int, seams: str | None) -> list[Path]:
    raw_dir = out_dir / "raw"
    report_path = raw_dir / "flatten_report.json"
    job = {"mesh": str(mesh.resolve()), "raw_dir": str(raw_dir),
           "unwrap": unwrap, "target_tris": target_tris,
           "seams": str(Path(seams).resolve()) if seams else None,
           "report": str(report_path)}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        f.write(json.dumps(job))
        job_path = f.name
    common.run_blender(common.SCRIPTS_DIR / "blender_flatten.py", [job_path],
                       log_name=f"flatten-{design}.log")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("errors"):
        print(f"warning: {len(report['errors'])} object(s) failed — "
              f"see {report_path}", file=sys.stderr)
    return [Path(s) for s in report["svgs"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--mesh", help="input mesh (.glb/.gltf/.obj/.fbx)")
    src.add_argument("--raw-svg", nargs="+",
                     help="already-exported raw SVG(s): skip Blender, post-process only")
    ap.add_argument("--design", required=True)
    ap.add_argument("--allowance-mm", type=float,
                    default=common.DEFAULT_SEAM_ALLOWANCE_MM)
    ap.add_argument("--target-tris", type=int, default=5000)
    ap.add_argument("--unwrap", default="ANGLE_BASED",
                    choices=["ANGLE_BASED", "CONFORMAL", "KEEP"])
    ap.add_argument("--seams", help="seams.json: {object_name: [[v1,v2],...]}")
    ap.add_argument("--min-area-mm2", type=float, default=100.0)
    ap.add_argument("--max-pieces", type=int, default=60,
                    help="fail loudly if the mesh fragments into more pieces")
    ap.add_argument("--out-dir", help="default: patterns/<design>")
    args = ap.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else common.PATTERNS_DIR / args.design
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mesh:
        svgs = run_blender_stage(Path(args.mesh), out_dir, args.design,
                                 args.unwrap, args.target_tris, args.seams)
    else:
        svgs = [Path(s) for s in args.raw_svg]
    if not svgs:
        print("no raw SVGs produced — check logs/", file=sys.stderr)
        sys.exit(3)

    polys: list[Polygon] = []
    for svg in svgs:
        polys.extend(parse_raw_svg(svg.read_text(encoding="utf-8"),
                                   args.min_area_mm2))
    if not polys:
        print("raw SVGs contained no usable pieces", file=sys.stderr)
        sys.exit(3)
    if len(polys) > args.max_pieces:
        print(f"{len(polys)} pieces parsed (max {args.max_pieces}) — the mesh "
              f"fragmented. Provide --seams, raise --min-area-mm2, or simplify "
              f"the mesh; a sewable garment has dozens of pieces, not hundreds.",
              file=sys.stderr)
        sys.exit(4)

    pieces = build_pieces(polys, args.allowance_mm)
    doc = common.pieces_doc(args.design, pieces, args.allowance_mm,
                            source_mesh=args.mesh or ",".join(map(str, args.raw_svg)))
    pieces_path = common.write_json(out_dir / "pieces.json", doc)
    svg_path = out_dir / f"{args.design}_pattern.svg"
    svg_path.write_text(pattern_sheet_svg(pieces, args.design), encoding="utf-8")
    print(f"{len(pieces)} piece(s) -> {pieces_path}")
    print(f"pattern sheet -> {svg_path}")


if __name__ == "__main__":
    main()
