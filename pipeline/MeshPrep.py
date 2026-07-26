"""MeshPrep — clean an imported 3D mesh via headless Blender.

Takes a mesh file (glb/gltf/obj/fbx), runs Blender in the background to
merge near-duplicate vertices, recalculate normals outward, count
non-manifold edges, and decimate down to a target triangle budget, then
exports a cleaned .glb plus a meshstats.json report.

CLI:
  python "pipeline/MeshPrep.py" --mesh designs/tote.glb --out designs/tote_clean.glb
      [--target-tris 5000] [--merge-dist 0.0005] [--stats path/to/meshstats.json]

Defaults: --out is <mesh>_clean.glb alongside the input; --stats is
meshstats.json alongside --out. All Blender work happens in
scripts/blender_meshprep.py behind common.run_blender(); this module only
writes a job JSON, launches Blender, and validates the results.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline import common  # noqa: E402

JOB_SCHEMA = "3dfabric.meshprep.job/1"
STATS_SCHEMA = "3dfabric.meshstats/1"
SUPPORTED_EXTS = {".glb", ".gltf", ".obj", ".fbx"}
BLENDER_SCRIPT = common.SCRIPTS_DIR / "blender_meshprep.py"

DEFAULT_TARGET_TRIS = 5000
DEFAULT_MERGE_DIST = 0.0005  # meters (Blender/glTF native unit)


def default_out_path(mesh: str | Path) -> Path:
    mesh = Path(mesh)
    return mesh.with_name(mesh.stem + "_clean.glb")


def default_stats_path(out: str | Path) -> Path:
    return Path(out).parent / "meshstats.json"


def build_job(mesh: str | Path, out: str | Path, target_tris: int,
              merge_dist: float, stats: str | Path) -> dict:
    """Assemble the job document handed to the Blender-side script."""
    mesh = Path(mesh).resolve()
    ext = mesh.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            f"unsupported mesh extension {ext!r} for {mesh}; "
            f"expected one of {sorted(SUPPORTED_EXTS)}")
    if target_tris <= 0:
        raise ValueError(f"--target-tris must be positive, got {target_tris}")
    if merge_dist < 0:
        raise ValueError(f"--merge-dist must be >= 0, got {merge_dist}")
    return {
        "schema": JOB_SCHEMA,
        "mesh": str(mesh),
        "out": str(Path(out).resolve()),
        "stats": str(Path(stats).resolve()),
        "target_tris": int(target_tris),
        "merge_dist": float(merge_dist),
        # Blender side copies this into meshstats.json so the Blender
        # script stays free of repo imports.
        "draft": common.draft_header("mesh stats"),
    }


def write_job(job: dict, path: str | Path | None = None) -> Path:
    """Write the job JSON; default location is a fresh temp file."""
    if path is None:
        fd = tempfile.NamedTemporaryFile(
            mode="w", suffix=".meshprep.json", prefix="3dfabric_",
            delete=False, encoding="utf-8")
        with fd:
            json.dump(job, fd, indent=2)
        return Path(fd.name)
    return common.write_json(path, job)


def run(mesh: str | Path, out: str | Path | None = None,
        target_tris: int = DEFAULT_TARGET_TRIS,
        merge_dist: float = DEFAULT_MERGE_DIST,
        stats: str | Path | None = None,
        timeout: int = 900) -> dict:
    """Clean `mesh` via Blender; returns the loaded meshstats dict."""
    mesh = Path(mesh)
    if not mesh.is_file():
        raise FileNotFoundError(f"input mesh not found: {mesh}")
    out = Path(out) if out else default_out_path(mesh)
    stats_path = Path(stats) if stats else default_stats_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    job = build_job(mesh, out, target_tris, merge_dist, stats_path)
    job_path = write_job(job)
    common.run_blender(BLENDER_SCRIPT, [str(job_path)], timeout=timeout,
                       log_name="meshprep.log")

    if not out.is_file():
        raise RuntimeError(f"Blender exited 0 but output missing: {out}")
    if not stats_path.is_file():
        raise RuntimeError(f"Blender exited 0 but stats missing: {stats_path}")
    doc = json.loads(stats_path.read_text(encoding="utf-8"))
    if doc.get("schema") != STATS_SCHEMA:
        raise ValueError(f"{stats_path}: not a {STATS_SCHEMA} document")
    job_path.unlink(missing_ok=True)  # keep only on failure, for debugging
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="MeshPrep",
        description="Clean a 3D mesh (merge doubles, fix normals, decimate) "
                    "via headless Blender and export a .glb + meshstats.json.")
    ap.add_argument("--mesh", required=True,
                    help="input mesh: .glb .gltf .obj or .fbx")
    ap.add_argument("--out", default=None,
                    help="output .glb (default: <mesh>_clean.glb alongside input)")
    ap.add_argument("--target-tris", type=int, default=DEFAULT_TARGET_TRIS,
                    help="triangle budget; decimate if over (default %(default)s)")
    ap.add_argument("--merge-dist", type=float, default=DEFAULT_MERGE_DIST,
                    help="merge-by-distance threshold in meters (default %(default)s)")
    ap.add_argument("--stats", default=None,
                    help="stats JSON path (default: meshstats.json alongside --out)")
    args = ap.parse_args(argv)

    try:
        doc = run(args.mesh, args.out, args.target_tris, args.merge_dist,
                  args.stats)
    except Exception as exc:  # CLI boundary: report, nonzero exit
        print(f"MeshPrep failed: {exc}", file=sys.stderr)
        return 1
    print(f"MeshPrep OK: {doc['objects']} object(s), "
          f"{doc['tris_before']} -> {doc['tris_after']} tris, "
          f"{doc['non_manifold_edges']} non-manifold edge(s) -> {doc['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
