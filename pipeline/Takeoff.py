"""Material takeoff: nesting.json + materials.yaml -> yardage/hide count + cost.

CLI:
  python pipeline/Takeoff.py --nesting "takeoffs/<design>/nesting.json"
      [--material canvas] [--qty 1 [10 50 ...]]
      [--materials "materials.yaml"] [--out-dir "takeoffs/<design>"]

Reads the nested-layout stats (3dfabric.nesting/1) and the material price
book, then writes to --out-dir (default takeoffs/<design>):

  takeoff.json   3dfabric.takeoff/1 — per-unit yardage/hide count + cost
  takeoff.csv    one data row per requested qty: design, material, qty,
                 yd (or hides) per unit, cost per unit, total cost

Yard goods (unit: yard): linear inches = nested used length; errors out if
the roll is narrower than the nested sheet width. Hides (unit: hide): hide
count approximated from total piece area with a stated packing assumption.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml

from pipeline import common

MM2_PER_IN2 = 645.16
# Stated packing assumption: only ~75% of a hide's bounding rectangle is
# usable once irregular hide edges and defects are accounted for.
HIDE_PACKING_EFFICIENCY = 0.75
HIDE_APPROX_NOTE = "hide math is an approximation"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_materials(path: str | Path | None = None) -> dict:
    """Load the material price book (materials.yaml). Returns the full doc."""
    path = Path(path) if path else common.MATERIALS_YAML
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "materials" not in doc:
        raise ValueError(f"{path}: no 'materials' section in price book")
    return doc


def load_nesting(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = doc.get("schema")
    # Tolerate a missing schema key (nesting module may predate it) but
    # reject documents that declare themselves as something else.
    if schema is not None and not str(schema).startswith("3dfabric.nesting"):
        raise ValueError(f"{path}: not a 3dfabric.nesting document "
                         f"(schema={schema!r})")
    if not doc.get("design"):
        doc["design"] = Path(path).resolve().parent.name
    return doc


def _used_length_in(nesting: dict) -> float:
    if nesting.get("used_length_in") is not None:
        return float(nesting["used_length_in"])
    if nesting.get("used_length_mm") is not None:
        return float(nesting["used_length_mm"]) / common.MM_PER_IN
    raise ValueError(
        "nesting.json has neither 'used_length_in' nor 'used_length_mm' — "
        "cannot compute linear yardage")


def _total_piece_area_mm2(nesting: dict) -> float:
    for key in ("total_piece_area_mm2", "piece_area_mm2"):
        if nesting.get(key) is not None:
            return float(nesting[key])
    raise ValueError(
        "nesting.json has no 'total_piece_area_mm2' — cannot compute hide "
        "count for a per-hide material")


# ---------------------------------------------------------------------------
# Takeoff math
# ---------------------------------------------------------------------------

def compute_takeoff(nesting: dict, material_key: str, materials_doc: dict,
                    qty: int = 1) -> dict:
    """Build a 3dfabric.takeoff/1 document (per-unit numbers, primary qty)."""
    materials = materials_doc["materials"]
    if material_key not in materials:
        raise KeyError(
            f"material '{material_key}' not in price book; "
            f"available: {sorted(materials)}")
    mat = materials[material_key]
    defaults = materials_doc.get("defaults") or {}

    waste_factor = float(mat.get("waste_factor",
                                 defaults.get("waste_factor", 0.10)))
    price_usd = float(mat["price_usd"])
    unit = str(mat.get("unit", "yard")).lower()

    assumptions = [
        "Prices in the material price book are DRAFT placeholders until "
        "verified against vendor quotes.",
        f"Waste factor {waste_factor:.0%} applied on top of the nested "
        f"layout.",
    ]

    if nesting.get("sheet_width_in") is not None:
        sheet_width_in = float(nesting["sheet_width_in"])
    elif nesting.get("sheet_width_mm") is not None:
        sheet_width_in = float(nesting["sheet_width_mm"]) / common.MM_PER_IN
    else:
        sheet_width_in = common.DEFAULT_SHEET_WIDTH_IN
        assumptions.append(
            f"nesting.json did not record a sheet width; assumed the "
            f"default {common.DEFAULT_SHEET_WIDTH_IN:g} in.")

    utilization = nesting.get("utilization")
    if utilization is not None:
        utilization = float(utilization)
        if utilization > 1.0:  # tolerate percent-style values from nesting
            utilization = utilization / 100.0
            assumptions.append(
                "Nesting utilization looked like a percentage; normalized "
                "to a fraction.")

    doc: dict = {
        "schema": "3dfabric.takeoff/1",
        "design": nesting["design"],
        "material": material_key,
        "material_display": mat.get("display", material_key),
        "unit": unit,
        "qty": int(qty),
        "sheet_width_in": sheet_width_in,
        "utilization": utilization,
        "waste_factor": waste_factor,
    }

    if unit == "yard":
        width_in = float(mat.get("width_in",
                                 defaults.get("fabric_width_in",
                                              common.DEFAULT_SHEET_WIDTH_IN)))
        if width_in < sheet_width_in:
            raise ValueError(
                f"Material '{material_key}' roll width {width_in:g} in is "
                f"narrower than the nested layout width {sheet_width_in:g} "
                f"in — re-run nesting at {width_in:g} in (or narrower) "
                f"before pricing this material.")
        linear_in = _used_length_in(nesting)
        yd_per_unit = linear_in / common.IN_PER_YD * (1.0 + waste_factor)
        cost_per_unit = yd_per_unit * price_usd
        doc["linear_yd_per_unit"] = round(yd_per_unit, 4)
        doc["material_cost_per_unit_usd"] = round(cost_per_unit, 2)
    elif unit == "hide":
        area_mm2 = _total_piece_area_mm2(nesting)
        sheet_w_in = float(mat["sheet_w_in"])
        sheet_h_in = float(mat["sheet_h_in"])
        usable_mm2 = (sheet_w_in * sheet_h_in * MM2_PER_IN2
                      * HIDE_PACKING_EFFICIENCY)
        hides_per_unit = math.ceil(area_mm2 * (1.0 + waste_factor)
                                   / usable_mm2)
        doc["hides_per_unit"] = hides_per_unit
        doc["material_cost_per_unit_usd"] = round(hides_per_unit * price_usd,
                                                  2)
        assumptions.append(HIDE_APPROX_NOTE)
        assumptions.append(
            f"Hide usable area = {sheet_w_in:g}x{sheet_h_in:g} in rectangle "
            f"at {HIDE_PACKING_EFFICIENCY:.0%} packing efficiency.")
    else:
        raise ValueError(
            f"material '{material_key}' has unknown unit {unit!r} "
            f"(expected 'yard' or 'hide')")

    doc["assumptions"] = assumptions
    doc["draft"] = common.draft_header("takeoff")
    return doc


def csv_rows(takeoff: dict, qtys: list[int]) -> list[list]:
    """Header + one row per requested qty line."""
    per_unit = takeoff.get("linear_yd_per_unit",
                           takeoff.get("hides_per_unit"))
    cost = takeoff["material_cost_per_unit_usd"]
    rows = [["design", "material", "qty", "yd_or_hides_per_unit",
             "cost_per_unit_usd", "total_cost_usd"]]
    for q in qtys:
        rows.append([takeoff["design"], takeoff["material"], int(q),
                     per_unit, cost, round(int(q) * cost, 2)])
    return rows


def write_outputs(takeoff: dict, qtys: list[int],
                  out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = common.write_json(out_dir / "takeoff.json", takeoff)
    csv_path = out_dir / "takeoff.csv"
    # newline="" keeps csv.writer from double-spacing rows on Windows
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(takeoff, qtys))
    return json_path, csv_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Material takeoff: nesting.json + materials.yaml -> "
                    "takeoff.json + takeoff.csv (yardage/hides + cost).")
    parser.add_argument("--nesting", required=True,
                        help="path to takeoffs/<design>/nesting.json")
    parser.add_argument("--material", default="canvas",
                        help="material key from the price book "
                             "(default: canvas)")
    parser.add_argument("--qty", type=int, nargs="+", default=[1],
                        metavar="N",
                        help="one or more order quantities; each becomes a "
                             "CSV line (default: 1)")
    parser.add_argument("--materials", default=str(common.MATERIALS_YAML),
                        help="material price book YAML "
                             "(default: repo materials.yaml)")
    parser.add_argument("--out-dir", default=None,
                        help="output directory "
                             "(default: takeoffs/<design>)")
    args = parser.parse_args(argv)

    nesting = load_nesting(args.nesting)
    materials_doc = load_materials(args.materials)
    takeoff = compute_takeoff(nesting, args.material, materials_doc,
                              qty=args.qty[0])
    out_dir = (Path(args.out_dir) if args.out_dir
               else common.TAKEOFFS_DIR / takeoff["design"])
    json_path, csv_path = write_outputs(takeoff, args.qty, out_dir)
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
