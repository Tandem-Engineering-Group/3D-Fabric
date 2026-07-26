"""Img2Mesh — single image -> 3D mesh (.glb) via local AI backends.

CLI:
    python "pipeline/Img2Mesh.py" --image designs/tote.jpg --out designs/tote.glb
        [--backend auto|triposr|trellis2|hunyuan3d]   (default: auto)
        [--no-remove-bg]                              (skip rembg background removal)
        [--mc-resolution 256]                         (marching cubes grid resolution)

Backends (auto picks the first AVAILABLE in this order):
    triposr    weights/triposr   + vendor/TripoSR run.py, executed in .venv-ai
    trellis2   weights/trellis2  (Windows runtime not stood up yet -> clear error)
    hunyuan3d  weights/hunyuan3d (Windows runtime not stood up yet -> clear error)

"Available" = the backend's weights dir is non-empty AND the AI venv python
(.venv-ai) exists. If no backend is available the CLI exits with code 2 and a
message reminding the user the pattern pipeline still runs end-to-end via a
primitive/user-supplied mesh (--mesh input to downstream stages).

Exit codes: 0 ok, 1 backend/inference failure, 2 no backend available,
3 backend recognized but its Windows runtime is not implemented yet.

Importable API: build_triposr_cmd(), pick_backend(), normalize_output(),
BACKENDS registry, availability probes.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import common

AI_PYTHON = common.REPO_ROOT / ".venv-ai" / "Scripts" / "python.exe"
VENDOR_TRIPOSR = common.REPO_ROOT / "vendor" / "TripoSR"
TRIPOSR_RUN_PY = VENDOR_TRIPOSR / "run.py"
TRIPOSR_WEIGHTS = common.WEIGHTS_DIR / "triposr"
TRELLIS2_WEIGHTS = common.WEIGHTS_DIR / "trellis2"
HUNYUAN3D_WEIGHTS = common.WEIGHTS_DIR / "hunyuan3d"

DEFAULT_MC_RESOLUTION = 256
DEFAULT_TIMEOUT_S = 1800

FALLBACK_HINT = (
    "The pattern pipeline still works end-to-end without AI meshing: pass an "
    "existing/primitive mesh to the downstream stages via --mesh."
)

# ---------------------------------------------------------------------------
# Known Windows landmine: vendor/TripoSR/tsr/models/isosurface.py does
# `from torchmcubes import marching_cubes` at import time. torchmcubes is a
# compiled C++/CUDA extension with no Windows wheels — it is very likely NOT
# installed in .venv-ai. We do NOT modify vendor/ in this module; instead the
# subprocess failure is detected (see classify_triposr_failure) and this
# documented patch is offered as the fix. Both shims are CPU-only, take
# (volume_tensor, threshold) and return (verts, faces) tensors exactly like
# torchmcubes' CPU path, so MarchingCubeHelper.forward needs no other change
# (its existing v_pos[..., [2, 1, 0]] swizzle over grid-index order still
# applies; verify mesh orientation visually after patching).
# ---------------------------------------------------------------------------
TORCHMCUBES_FALLBACK_PATCH = '''\
# Drop-in patch for vendor/TripoSR/tsr/models/isosurface.py
# Replace the single line:
#     from torchmcubes import marching_cubes
# with the block below (keeps torchmcubes as the fast path when present):
import torch
try:
    from torchmcubes import marching_cubes
except ImportError:
    try:
        import mcubes  # pip install pymcubes  (pure CPU, no compiler needed)

        def marching_cubes(level, thresh):
            verts, faces = mcubes.marching_cubes(
                level.detach().cpu().numpy(), thresh)
            return (torch.from_numpy(verts.copy()).float(),
                    torch.from_numpy(faces.copy()).long())
    except ImportError:
        from skimage import measure  # pip install scikit-image

        def marching_cubes(level, thresh):
            verts, faces, _normals, _values = measure.marching_cubes(
                level.detach().cpu().numpy(), thresh)
            return (torch.from_numpy(verts.copy()).float(),
                    torch.from_numpy(faces.copy()).long())
'''

TORCHMCUBES_ERROR = (
    "TripoSR failed: the 'torchmcubes' compiled extension is missing or broken "
    "in .venv-ai (no Windows wheels; building needs MSVC + CUDA toolchain).\n"
    "Fix options:\n"
    f'  1) Build it:  & "{AI_PYTHON}" -m pip install '
    "git+https://github.com/tatsy/torchmcubes.git\n"
    "     (requires Visual Studio Build Tools; CPU-only build is sufficient)\n"
    "  2) Patch vendor/TripoSR to a pure-CPU marching cubes: install pymcubes "
    "or scikit-image into .venv-ai and apply the exact drop-in patch in "
    "pipeline.Img2Mesh.TORCHMCUBES_FALLBACK_PATCH to "
    "vendor/TripoSR/tsr/models/isosurface.py.\n"
    "Full subprocess log: logs/img2mesh_triposr.log"
)


class Img2MeshError(RuntimeError):
    exit_code = 1


class NoBackendAvailableError(Img2MeshError):
    exit_code = 2


class BackendNotImplementedError(Img2MeshError):
    exit_code = 3


# ---------------------------------------------------------------------------
# Availability probes
# ---------------------------------------------------------------------------

def _dir_nonempty(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def triposr_available() -> bool:
    # TSR.from_pretrained hard-requires config.yaml + model.ckpt in the
    # weights dir; probing for them avoids launching against a half-download.
    return (
        AI_PYTHON.is_file()
        and TRIPOSR_RUN_PY.is_file()
        and _dir_nonempty(TRIPOSR_WEIGHTS)
        and (TRIPOSR_WEIGHTS / "config.yaml").is_file()
        and (TRIPOSR_WEIGHTS / "model.ckpt").is_file()
    )


def trellis2_available() -> bool:
    return AI_PYTHON.is_file() and _dir_nonempty(TRELLIS2_WEIGHTS)


def hunyuan3d_available() -> bool:
    return AI_PYTHON.is_file() and _dir_nonempty(HUNYUAN3D_WEIGHTS)


# ---------------------------------------------------------------------------
# TripoSR backend
# ---------------------------------------------------------------------------

def build_triposr_cmd(image: str | Path, out: str | Path,
                      opts: dict | None = None) -> list[str]:
    """Pure builder for the TripoSR subprocess argv (list form: no shell
    quoting needed even with spaces in every path). Caller must run it with
    cwd=VENDOR_TRIPOSR because run.py imports the sibling `tsr` package."""
    opts = dict(opts or {})
    python = str(opts.get("python", AI_PYTHON))
    # The subprocess runs with cwd=VENDOR_TRIPOSR, so every filesystem path
    # in the argv must be pinned absolute against the CALLER's cwd here —
    # a relative --image like "designs/tote.jpg" would otherwise resolve
    # inside vendor/TripoSR in the child and fail.
    weights = str(Path(opts.get("weights", TRIPOSR_WEIGHTS)).resolve())
    output_dir = str(Path(opts.get(
        "output_dir", Path(out).parent / "_triposr_staging")).resolve())
    cmd = [
        python,
        str(TRIPOSR_RUN_PY),
        str(Path(image).resolve()),
        "--pretrained-model-name-or-path", weights,
        "--model-save-format", "glb",
        "--output-dir", output_dir,
        "--mc-resolution", str(opts.get("mc_resolution", DEFAULT_MC_RESOLUTION)),
    ]
    if opts.get("no_remove_bg"):
        cmd.append("--no-remove-bg")
    return cmd


# Import-time failure signatures only. isosurface.py prints a benign
# "torchmcubes was not compiled with CUDA support" line on runs where the
# import SUCCEEDED, so a bare "torchmcubes" substring check would misdiagnose
# a later failure (e.g. CUDA OOM) as a missing extension.
_TORCHMCUBES_IMPORT_FAILURE = re.compile(
    r"No module named ['\"]?torchmcubes"
    r"|ImportError:.*torchmcubes"
    r"|DLL load failed.*torchmcubes"
    r"|torchmcubes.*DLL load failed")


def classify_triposr_failure(returncode: int, stdout: str, stderr: str) -> str:
    blob = f"{stdout}\n{stderr}"
    if _TORCHMCUBES_IMPORT_FAILURE.search(blob):
        return TORCHMCUBES_ERROR
    tail = blob[-2000:].strip()
    return (f"TripoSR subprocess exited {returncode}.\n--- output tail ---\n"
            f"{tail}\nFull log: logs/img2mesh_triposr.log")


def normalize_output(output_dir: str | Path, out: str | Path) -> Path:
    """Find the mesh TripoSR wrote somewhere under output_dir (it emits
    <output_dir>/<i>/mesh.glb or mesh.obj) and normalize it to the exact
    requested `out` path, converting format via trimesh when needed."""
    output_dir = Path(output_dir)
    out = Path(out)
    candidates: list[Path] = []
    for ext in (".glb", ".obj", ".ply", ".stl"):
        candidates.extend(sorted(output_dir.rglob(f"*{ext}")))
    if not candidates:
        raise Img2MeshError(f"backend reported success but no mesh file was "
                            f"found under {output_dir}")

    def rank(p: Path) -> tuple[int, int]:
        same_ext = 0 if p.suffix.lower() == out.suffix.lower() else 1
        named_mesh = 0 if p.stem.lower() == "mesh" else 1
        return (same_ext, named_mesh)

    src = min(candidates, key=rank)
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == out.suffix.lower():
        shutil.copyfile(src, out)
    else:
        import trimesh  # lazy: keep --help and probes fast
        trimesh.load(src, force="mesh").export(out)
    return out


def _write_log(name: str, cmd: list[str],
               proc: subprocess.CompletedProcess) -> None:
    common.LOGS_DIR.mkdir(exist_ok=True)
    (common.LOGS_DIR / name).write_text(
        f"cmd: {cmd}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n"
        f"{proc.stderr}", encoding="utf-8")


def run_triposr(image: str | Path, out: str | Path, opts: dict | None = None) -> int:
    opts = dict(opts or {})
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="img2mesh_triposr_") as staging:
        cmd = build_triposr_cmd(image, out, {**opts, "output_dir": staging})
        timeout_s = opts.get("timeout_s", DEFAULT_TIMEOUT_S)
        try:
            # utf-8 + replace: child output is not guaranteed to decode under
            # the Windows default cp1252 codec.
            proc = subprocess.run(cmd, cwd=str(VENDOR_TRIPOSR),
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise Img2MeshError(
                f"TripoSR timed out after {timeout_s}s. Try a lower "
                f"--mc-resolution or a smaller input image, or raise "
                f"opts['timeout_s'].") from exc
        _write_log("img2mesh_triposr.log", cmd, proc)
        if proc.returncode != 0:
            raise Img2MeshError(
                classify_triposr_failure(proc.returncode, proc.stdout,
                                         proc.stderr))
        normalize_output(staging, out)
    print(f"wrote {out}\n{common.draft_header('mesh')}")
    return 0


def run_trellis2(image: str | Path, out: str | Path, opts: dict | None = None) -> int:
    raise BackendNotImplementedError(
        "trellis2: weights present; Windows runtime not yet stood up — "
        "use --backend triposr")


def run_hunyuan3d(image: str | Path, out: str | Path, opts: dict | None = None) -> int:
    raise BackendNotImplementedError(
        "hunyuan3d: weights present; Windows runtime not yet stood up — "
        "use --backend triposr")


# ---------------------------------------------------------------------------
# Backend registry + selection
# ---------------------------------------------------------------------------

BACKEND_ORDER = ("triposr", "trellis2", "hunyuan3d")

BACKENDS: dict[str, dict] = {
    "triposr": {"available": triposr_available, "run": run_triposr},
    "trellis2": {"available": trellis2_available, "run": run_trellis2},
    "hunyuan3d": {"available": hunyuan3d_available, "run": run_hunyuan3d},
}


def pick_backend(requested: str = "auto") -> str:
    if requested != "auto":
        if requested not in BACKENDS:
            raise NoBackendAvailableError(
                f"unknown backend '{requested}'; choose from "
                f"{', '.join(BACKEND_ORDER)} or auto")
        if not BACKENDS[requested]["available"]():
            raise NoBackendAvailableError(
                f"backend '{requested}' is not available yet (weights dir "
                f"empty/incomplete or .venv-ai missing — likely still "
                f"downloading). {FALLBACK_HINT}")
        return requested
    for name in BACKEND_ORDER:
        if BACKENDS[name]["available"]():
            return name
    raise NoBackendAvailableError(
        "no image->3D backend is available yet (model weights and/or the "
        ".venv-ai runtime are still downloading/installing). " + FALLBACK_HINT)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Img2Mesh",
        description="Turn a single purse photo/sketch into a 3D mesh (.glb) "
                    "using a local AI backend.",
        epilog=FALLBACK_HINT)
    parser.add_argument("--image", required=True,
                        help="input image (.jpg/.png)")
    parser.add_argument("--out", required=True,
                        help="output mesh path (.glb recommended)")
    parser.add_argument("--backend", default="auto",
                        choices=("auto",) + BACKEND_ORDER,
                        help="backend to use; auto picks the first available "
                             "of: %s (default: auto)" % ", ".join(BACKEND_ORDER))
    parser.add_argument("--no-remove-bg", action="store_true",
                        help="skip automatic background removal (input must "
                             "already be a clean RGB image)")
    parser.add_argument("--mc-resolution", type=int,
                        default=DEFAULT_MC_RESOLUTION,
                        help="marching cubes grid resolution "
                             f"(default: {DEFAULT_MC_RESOLUTION})")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    image = Path(args.image)
    if not image.is_file():
        print(f"input image not found: {image}", file=sys.stderr)
        return 1
    try:
        backend = pick_backend(args.backend)
    except NoBackendAvailableError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    opts = {"mc_resolution": args.mc_resolution,
            "no_remove_bg": args.no_remove_bg}
    try:
        return BACKENDS[backend]["run"](str(image), args.out, opts)
    except Img2MeshError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
