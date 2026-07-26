"""Tech pack generator: pieces.json + takeoff.json -> techpack/<design>.md.

CLI:
  python pipeline/TechPack.py --pieces "patterns/<design>/pieces.json"
      --takeoff "takeoffs/<design>/takeoff.json"
      [--mesh-stats "<meshstats.json>"] [--out-dir "techpack"]

Writes techpack/<design>.md with: DRAFT banner, Overview (design, date,
source mesh, overall bbox in mm and inches), Pattern pieces table,
Materials & takeoff, Hardware BOM stub, Construction notes stub, and the
seam allowance note. All numbers come from the upstream JSON contracts;
nothing here re-measures geometry beyond bounding boxes and ring areas.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import common

HARDWARE_STUB = [
    ("Zipper", "TBD", "TBD — length/gauge per opening"),
    ("Rivets", "TBD", "TBD — size/finish"),
    ("D-rings", "TBD", "TBD — strap width match"),
    ("Magnetic snap", "TBD", "TBD — closure spec"),
]

CONSTRUCTION_STUB = [
    "Cut all pieces per the pattern sheet (cut lines include seam "
    "allowance); observe grainlines.",
    "Mark notches, stitch lines, and hardware placement on the wrong side.",
    "Assemble gusset to body panels, right sides together, along the "
    "stitch lines.",
    "Attach straps and hardware before closing the top edge.",
    "Hem/topstitch the opening; final press and inspect.",
]


# ---------------------------------------------------------------------------
# Loaders / geometry
# ---------------------------------------------------------------------------

def load_takeoff(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = doc.get("schema")
    if schema is not None and not str(schema).startswith("3dfabric.takeoff"):
        raise ValueError(f"{path}: not a 3dfabric.takeoff document "
                         f"(schema={schema!r})")
    return doc


def load_mesh_stats(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: mesh stats must be a JSON object")
    return doc


def piece_area_cm2(piece: dict) -> float:
    """Net piece area (exterior minus holes) in cm^2."""
    area = common.ring_area_mm2(piece["polygon"])
    for hole in piece.get("holes", []):
        area -= common.ring_area_mm2(hole)
    return area / 100.0


def overall_bbox_mm(pieces: list) -> tuple[float, float, float, float]:
    boxes = [common.bbox_of(p["polygon"]) for p in pieces]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _mm_and_in(w_mm: float, h_mm: float) -> str:
    return (f"{w_mm:.0f} × {h_mm:.0f} mm "
            f"({common.mm_to_in(w_mm):.2f} × {common.mm_to_in(h_mm):.2f} in)")


# ---------------------------------------------------------------------------
# Markdown assembly
# ---------------------------------------------------------------------------

def build_techpack_md(pieces_doc: dict, takeoff: dict,
                      mesh_stats: dict | None = None) -> str:
    design = pieces_doc.get("design") or takeoff.get("design", "unknown")
    pieces = pieces_doc["pieces"]
    minx, miny, maxx, maxy = overall_bbox_mm(pieces)
    total_cuts = sum(int(p.get("cut_qty", 1)) for p in pieces)

    lines: list[str] = []
    lines.append(f"# Tech Pack — {design}")
    lines.append("")
    lines.append(f"> **{common.draft_header('tech pack')}**")
    lines.append("")

    # -- Overview -----------------------------------------------------------
    lines.append("## Overview")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Design | {design} |")
    lines.append(f"| Date | {date.today().isoformat()} |")
    lines.append(f"| Source mesh | {pieces_doc.get('source_mesh') or 'n/a'} |")
    lines.append(f"| Overall pattern bbox | "
                 f"{_mm_and_in(maxx - minx, maxy - miny)} |")
    lines.append(f"| Pattern pieces | {len(pieces)} pieces, "
                 f"{total_cuts} total cuts |")
    lines.append("")
    if mesh_stats:
        lines.append("### Mesh stats")
        lines.append("")
        for key, value in mesh_stats.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # -- Pattern pieces -----------------------------------------------------
    lines.append("## Pattern pieces")
    lines.append("")
    lines.append("| Label | Name | Cut qty | W × H (mm) | Area (cm²) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for piece in pieces:
        bx0, by0, bx1, by1 = common.bbox_of(piece["polygon"])
        lines.append(
            f"| {piece.get('label', '')} "
            f"| {piece.get('name', piece.get('id', ''))} "
            f"| {piece.get('cut_qty', 1)} "
            f"| {bx1 - bx0:.0f} × {by1 - by0:.0f} "
            f"| {piece_area_cm2(piece):.1f} |")
    lines.append("")

    # -- Materials & takeoff ------------------------------------------------
    lines.append("## Materials & takeoff")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Material | {takeoff.get('material_display', '')} "
                 f"(`{takeoff.get('material', '')}`) |")
    utilization = takeoff.get("utilization")
    util_str = f"{utilization * 100:.1f}%" if utilization is not None else "n/a"
    lines.append(f"| Nested utilization | {util_str} |")
    if takeoff.get("linear_yd_per_unit") is not None:
        lines.append(f"| Linear yd per unit | "
                     f"{takeoff['linear_yd_per_unit']:.3f} yd |")
    if takeoff.get("hides_per_unit") is not None:
        lines.append(f"| Hides per unit | {takeoff['hides_per_unit']} |")
    lines.append(f"| Material cost per unit | "
                 f"${takeoff.get('material_cost_per_unit_usd', 0):.2f} |")
    if takeoff.get("waste_factor") is not None:
        lines.append(f"| Waste factor | {takeoff['waste_factor']:.0%} |")
    if takeoff.get("sheet_width_in") is not None:
        lines.append(f"| Nested sheet width | "
                     f"{takeoff['sheet_width_in']:g} in |")
    lines.append("")
    assumptions = takeoff.get("assumptions") or []
    if assumptions:
        lines.append("Assumptions:")
        lines.append("")
        for note in assumptions:
            lines.append(f"- {note}")
        lines.append("")

    # -- Hardware BOM (stub) ------------------------------------------------
    lines.append("## Hardware BOM")
    lines.append("")
    lines.append("| Item | Qty | Spec |")
    lines.append("| --- | --- | --- |")
    for item, qty, spec in HARDWARE_STUB:
        lines.append(f"| {item} | {qty} | {spec} |")
    lines.append("")

    # -- Construction notes (stub) ------------------------------------------
    lines.append("## Construction notes")
    lines.append("")
    for i, step in enumerate(CONSTRUCTION_STUB, start=1):
        lines.append(f"{i}. {step}")
    lines.append("")

    # -- Seam allowance -----------------------------------------------------
    sa = pieces_doc.get("seam_allowance_mm",
                        common.DEFAULT_SEAM_ALLOWANCE_MM)
    lines.append("## Seam allowance")
    lines.append("")
    lines.append(f"All cut lines include a {sa:g} mm seam allowance; stitch "
                 f"lines are inset by the same amount. Verify before "
                 f"cutting production material.")
    lines.append("")
    return "\n".join(lines)


def write_techpack(pieces_doc: dict, takeoff: dict,
                   mesh_stats: dict | None = None,
                   out_dir: str | Path | None = None) -> Path:
    design = pieces_doc.get("design") or takeoff.get("design", "unknown")
    out_dir = Path(out_dir) if out_dir else common.TECHPACK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{design}.md"
    out_path.write_text(build_techpack_md(pieces_doc, takeoff, mesh_stats),
                        encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a DRAFT tech pack markdown from pieces.json "
                    "+ takeoff.json.")
    parser.add_argument("--pieces", required=True,
                        help="path to patterns/<design>/pieces.json")
    parser.add_argument("--takeoff", required=True,
                        help="path to takeoffs/<design>/takeoff.json")
    parser.add_argument("--mesh-stats", default=None,
                        help="optional meshstats.json with source-mesh "
                             "metrics")
    parser.add_argument("--out-dir", default=str(common.TECHPACK_DIR),
                        help="output directory (default: techpack/)")
    args = parser.parse_args(argv)

    pieces_doc = common.load_pieces(args.pieces)
    takeoff = load_takeoff(args.takeoff)
    mesh_stats = load_mesh_stats(args.mesh_stats) if args.mesh_stats else None
    out_path = write_techpack(pieces_doc, takeoff, mesh_stats,
                              out_dir=args.out_dir)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
