"""3D-Fabric one-command pipeline.

  python run_pipeline.py --mesh "designs/FeltCheckTote.glb" --name FeltCheckTote
  python run_pipeline.py --image "designs/sketch.jpg" --name HoboV1 --material leather_fullgrain

Chains: [Img2Mesh] -> MeshPrep -> SeamsAndFlatten -> Nesting -> Takeoff -> TechPack.
Each stage is that module's CLI in a subprocess, so any stage can also be run alone.
Outputs: patterns/<name>/, takeoffs/<name>/, techpack/<name>.md — all DRAFT-stamped.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
PIPELINE = REPO / "pipeline"
LOGS = REPO / "logs"


def stage(title: str, cmd: list[str], log) -> None:
    print(f"\n=== {title} ===", flush=True)
    print(" ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd), file=log, flush=True)
    t0 = time.time()
    proc = subprocess.run([str(c) for c in cmd], text=True,
                          capture_output=True, cwd=str(REPO))
    log.write(proc.stdout + "\n" + proc.stderr + "\n")
    log.flush()
    dt = time.time() - t0
    if proc.returncode != 0:
        tail = (proc.stdout + "\n" + proc.stderr).strip()[-1500:]
        print(tail)
        print(f"FAILED after {dt:.1f}s — full log: {log.name}")
        sys.exit(proc.returncode or 1)
    print(f"ok ({dt:.1f}s)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="input sketch/photo (uses Img2Mesh AI backend)")
    src.add_argument("--mesh", help="input 3D mesh (.glb/.obj) — skips the AI leg")
    ap.add_argument("--name", required=True, help="design name (folder + file naming)")
    ap.add_argument("--width", type=float, default=54.0, help="sheet width, inches")
    ap.add_argument("--material", default="canvas", help="key in materials.yaml")
    ap.add_argument("--allowance-mm", type=float, default=10.0, help="seam allowance")
    ap.add_argument("--target-tris", type=int, default=5000)
    ap.add_argument("--seams", help="optional seams.json edge markup")
    ap.add_argument("--qty", type=int, default=1, help="units for the takeoff")
    ap.add_argument("--backend", default="auto", help="Img2Mesh backend")
    ap.add_argument("--skip-meshprep", action="store_true")
    args = ap.parse_args()

    py = sys.executable
    name = args.name
    work = REPO / "designs" / name
    work.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    t_start = time.time()

    with open(LOGS / f"pipeline-{name}.log", "w", encoding="utf-8") as log:
        mesh = args.mesh
        if args.image:
            mesh = work / f"{name}_ai.glb"
            stage("Img2Mesh", [py, PIPELINE / "Img2Mesh.py",
                               "--image", args.image, "--out", mesh,
                               "--backend", args.backend], log)

        prepped = mesh
        if not args.skip_meshprep:
            prepped = work / f"{name}_prepped.glb"
            stage("MeshPrep", [py, PIPELINE / "MeshPrep.py",
                               "--mesh", mesh, "--out", prepped,
                               "--target-tris", args.target_tris], log)

        flatten_cmd = [py, PIPELINE / "SeamsAndFlatten.py",
                       "--mesh", prepped, "--design", name,
                       "--allowance-mm", args.allowance_mm,
                       "--target-tris", args.target_tris]
        if args.seams:
            flatten_cmd += ["--seams", args.seams]
        stage("SeamsAndFlatten", flatten_cmd, log)

        pieces = REPO / "patterns" / name / "pieces.json"
        stage("Nesting", [py, PIPELINE / "Nesting.py",
                          "--pieces", pieces, "--width-in", args.width], log)

        nesting = REPO / "takeoffs" / name / "nesting.json"
        stage("Takeoff", [py, PIPELINE / "Takeoff.py",
                          "--nesting", nesting, "--material", args.material,
                          "--qty", args.qty], log)

        takeoff = REPO / "takeoffs" / name / "takeoff.json"
        techpack_cmd = [py, PIPELINE / "TechPack.py",
                        "--pieces", pieces, "--takeoff", takeoff]
        stats = Path(str(prepped)).with_name("meshstats.json")
        if stats.exists():
            techpack_cmd += ["--mesh-stats", stats]
        stage("TechPack", techpack_cmd, log)

    print(f"\nDone in {time.time() - t_start:.1f}s — outputs:")
    for p in (REPO / "patterns" / name, REPO / "takeoffs" / name,
              REPO / "techpack" / f"{name}.md"):
        print(f"  {p}")
    print("All artifacts are DRAFT — unverified until a human approves.")


if __name__ == "__main__":
    main()
