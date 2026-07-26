"""3D-Fabric shared contracts and helpers.

This module is the single source of truth for how pipeline stages talk to each
other. Every module reads/writes these artifacts:

  patterns/<design>/pieces.json      piece geometry contract (see PIECES_SCHEMA)
  patterns/<design>/<design>_pattern.svg   labeled pattern sheet, 1 unit = 1 mm
  takeoffs/<design>/nesting.json     nested layout stats (see NESTING_SCHEMA)
  takeoffs/<design>/nested_<W>in.svg nested cut layout, 1 unit = 1 mm
  takeoffs/<design>/takeoff.json     yardage + cost (see TAKEOFF_SCHEMA)
  techpack/<design>.md               human spec sheet

Conventions:
  * All SVG outputs use 1 user unit = 1 millimeter, viewBox from (0,0),
    y-down. Each piece lives in <g id="piece-<n>" class="piece"> with a
    <title> child naming it.
  * pieces.json polygons are exterior rings, mm, counter-clockwise, first
    point NOT repeated at the end. "holes" is a list of interior rings.
  * The cut line (with seam allowance) is the polygon; the stitch line is
    polygon inset by seam_allowance_mm (stored separately when present).
  * Every generated artifact carries a DRAFT header until a human approves.

Blender is always driven as a subprocess:
  run_blender(script, args) -> blender --background --python script -- args
Blender-side scripts communicate via JSON files, never stdout parsing.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = REPO_ROOT / "patterns"
TAKEOFFS_DIR = REPO_ROOT / "takeoffs"
TECHPACK_DIR = REPO_ROOT / "techpack"
DESIGNS_DIR = REPO_ROOT / "designs"
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEIGHTS_DIR = REPO_ROOT / "weights"
LOGS_DIR = REPO_ROOT / "logs"
MATERIALS_YAML = REPO_ROOT / "materials.yaml"

MM_PER_IN = 25.4
IN_PER_YD = 36.0

DEFAULT_SHEET_WIDTH_IN = 54.0
DEFAULT_SEAM_ALLOWANCE_MM = 10.0


def draft_header(kind: str = "artifact") -> str:
    """One-line provenance stamp for generated files (goes in a comment)."""
    return (f"DRAFT — unverified {kind}, generated {date.today().isoformat()} "
            f"by 3D-Fabric pipeline. AI drafts, engineers seal.")


# ---------------------------------------------------------------------------
# Piece / nesting / takeoff data contracts
# ---------------------------------------------------------------------------

@dataclass
class Piece:
    """One pattern piece. Geometry in mm; polygon is the CUT line."""
    id: str                      # "piece-1"
    name: str                    # "body_front"
    label: str                   # short letter for the printed pattern, "A"
    polygon: list                # [[x, y], ...] exterior ring, mm
    holes: list = field(default_factory=list)
    stitch_polygon: list | None = None   # inset stitch line, when known
    cut_qty: int = 1
    grainline_deg: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def pieces_doc(design: str, pieces: list, seam_allowance_mm: float,
               source_mesh: str | None = None, extra: dict | None = None) -> dict:
    doc = {
        "schema": "3dfabric.pieces/1",
        "design": design,
        "units": "mm",
        "seam_allowance_mm": seam_allowance_mm,
        "source_mesh": source_mesh,
        "draft": draft_header("pattern pieces"),
        "pieces": [p.to_dict() if isinstance(p, Piece) else p for p in pieces],
    }
    if extra:
        doc.update(extra)
    return doc


def load_pieces(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "3dfabric.pieces/1":
        raise ValueError(f"{path}: not a 3dfabric.pieces/1 document")
    return doc


def write_json(path: str | Path, doc: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# SVG helpers (1 user unit = 1 mm)
# ---------------------------------------------------------------------------

def svg_open(width_mm: float, height_mm: float, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm}mm" height="{height_mm}mm" '
        f'viewBox="0 0 {width_mm:.3f} {height_mm:.3f}">\n'
        f'<!-- {draft_header("SVG")} -->\n'
        f'<title>{title}</title>\n'
    )


def polygon_points(ring: list) -> str:
    return " ".join(f"{x:.3f},{y:.3f}" for x, y in ring)


def piece_group_svg(piece: dict, transform: str = "",
                    stroke: str = "#111", fill: str = "none",
                    label_font_mm: float = 14.0) -> str:
    """Render one piece (cut line, optional stitch line, centered label)."""
    ring = piece["polygon"]
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    t = f' transform="{transform}"' if transform else ""
    out = [f'<g id="{piece["id"]}" class="piece"{t}>',
           f'<title>{piece.get("name", piece["id"])}</title>',
           f'<polygon points="{polygon_points(ring)}" fill="{fill}" '
           f'stroke="{stroke}" stroke-width="0.5"/>']
    for hole in piece.get("holes", []):
        out.append(f'<polygon points="{polygon_points(hole)}" fill="#fff" '
                   f'stroke="{stroke}" stroke-width="0.5"/>')
    sp = piece.get("stitch_polygon")
    if sp:
        out.append(f'<polygon points="{polygon_points(sp)}" fill="none" '
                   f'stroke="#c33" stroke-width="0.35" '
                   f'stroke-dasharray="4 2"/>')
    label = piece.get("label", "")
    name = piece.get("name", "")
    out.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{label_font_mm}" '
               f'text-anchor="middle" font-family="sans-serif">{label}'
               f'<tspan x="{cx:.1f}" dy="{label_font_mm}" '
               f'font-size="{label_font_mm * 0.45}">{name}</tspan></text>')
    out.append("</g>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Blender subprocess boundary
# ---------------------------------------------------------------------------

_BLENDER_GLOBS = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
]


def find_blender() -> str:
    """Locate blender.exe: $BLENDER_EXE first, then Program Files (newest)."""
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).is_file():
        return env
    hits: list[str] = []
    for pattern in _BLENDER_GLOBS:
        hits.extend(glob.glob(pattern))
    if not hits:
        raise FileNotFoundError(
            "blender.exe not found. Install Blender LTS or set BLENDER_EXE.")
    return sorted(hits)[-1]


def run_blender(script: str | Path, script_args: list[str] | None = None,
                timeout: int = 900, log_name: str | None = None) -> subprocess.CompletedProcess:
    """Run a Blender-side python script headless. Raises on nonzero exit."""
    exe = find_blender()
    cmd = [exe, "--background", "--python", str(script)]
    if script_args:
        cmd += ["--"] + [str(a) for a in script_args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if log_name:
        LOGS_DIR.mkdir(exist_ok=True)
        (LOGS_DIR / log_name).write_text(
            f"cmd: {cmd}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
            encoding="utf-8")
    if proc.returncode != 0:
        tail = (proc.stdout + "\n" + proc.stderr)[-2000:]
        raise RuntimeError(f"Blender exited {proc.returncode} for {script}:\n{tail}")
    return proc


def blender_available() -> bool:
    try:
        find_blender()
        return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Geometry conveniences (shapely optional at import time)
# ---------------------------------------------------------------------------

def ring_area_mm2(ring: list) -> float:
    """Shoelace area of a ring given as [[x, y], ...]."""
    n = len(ring)
    s = 0.0
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def bbox_of(ring: list) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def mm_to_in(mm: float) -> float:
    return mm / MM_PER_IN


def in_to_yd(inches: float) -> float:
    return inches / IN_PER_YD
