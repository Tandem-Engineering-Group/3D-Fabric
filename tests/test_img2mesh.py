"""Smoke tests for pipeline/Img2Mesh.py. No GPU, no model inference."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import Img2Mesh  # noqa: E402

MODULE = REPO_ROOT / "pipeline" / "Img2Mesh.py"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------

def test_help_exits_zero():
    proc = subprocess.run([sys.executable, str(MODULE), "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "--backend" in proc.stdout
    assert "--mc-resolution" in proc.stdout
    assert "--no-remove-bg" in proc.stdout


def test_cli_choices_match_registry():
    assert set(Img2Mesh.BACKEND_ORDER) == set(Img2Mesh.BACKENDS)


# ---------------------------------------------------------------------------
# build_triposr_cmd — pure argv builder
# ---------------------------------------------------------------------------

def test_build_triposr_cmd_list_and_weights():
    cmd = Img2Mesh.build_triposr_cmd(
        "C:/some dir/photo with space.png", "C:/out dir/mesh.glb",
        {"mc_resolution": 128, "no_remove_bg": True,
         "output_dir": "C:/stage dir"})
    # list-form argv: every element a plain str, no manual shell quoting
    assert isinstance(cmd, list)
    assert all(isinstance(c, str) for c in cmd)
    assert not any(c.startswith('"') or c.endswith('"') for c in cmd)

    assert cmd[0] == str(Img2Mesh.AI_PYTHON)
    assert cmd[1] == str(Img2Mesh.TRIPOSR_RUN_PY)
    assert cmd[2] == str(Path("C:/some dir/photo with space.png").resolve())

    i = cmd.index("--pretrained-model-name-or-path")
    assert cmd[i + 1] == str(Img2Mesh.TRIPOSR_WEIGHTS)

    assert cmd[cmd.index("--model-save-format") + 1] == "glb"
    assert cmd[cmd.index("--output-dir") + 1] == str(
        Path("C:/stage dir").resolve())
    assert cmd[cmd.index("--mc-resolution") + 1] == "128"
    assert "--no-remove-bg" in cmd


def test_build_triposr_cmd_defaults():
    cmd = Img2Mesh.build_triposr_cmd("in.png", "out/mesh.glb")
    assert cmd[cmd.index("--mc-resolution") + 1] == str(
        Img2Mesh.DEFAULT_MC_RESOLUTION)
    assert "--no-remove-bg" not in cmd
    assert str(Img2Mesh.TRIPOSR_WEIGHTS) in cmd


def test_build_triposr_cmd_pins_relative_paths_absolute(monkeypatch, tmp_path):
    # regression: the subprocess runs with cwd=vendor/TripoSR, so a relative
    # --image (the module docstring's own example) must be resolved against
    # the CALLER's cwd before the argv is built
    monkeypatch.chdir(tmp_path)
    cmd = Img2Mesh.build_triposr_cmd("designs/tote.jpg", "designs/tote.glb")
    assert Path(cmd[2]).is_absolute()
    assert Path(cmd[2]) == (tmp_path / "designs" / "tote.jpg").resolve()
    out_dir = Path(cmd[cmd.index("--output-dir") + 1])
    assert out_dir.is_absolute()
    assert out_dir == (tmp_path / "designs" / "_triposr_staging").resolve()


# ---------------------------------------------------------------------------
# Backend auto-selection (availability probes monkeypatched)
# ---------------------------------------------------------------------------

def _set_available(monkeypatch, **flags):
    for name, flag in flags.items():
        monkeypatch.setitem(Img2Mesh.BACKENDS[name], "available",
                            lambda flag=flag: flag)


def test_pick_backend_none_available_raises_exit2(monkeypatch):
    _set_available(monkeypatch, triposr=False, trellis2=False, hunyuan3d=False)
    with pytest.raises(Img2Mesh.NoBackendAvailableError) as exc:
        Img2Mesh.pick_backend("auto")
    assert exc.value.exit_code == 2
    assert "--mesh" in str(exc.value)  # points user at the non-AI path


def test_main_none_available_returns_2(monkeypatch, tmp_path):
    _set_available(monkeypatch, triposr=False, trellis2=False, hunyuan3d=False)
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")  # existence is all main checks
    rc = Img2Mesh.main(["--image", str(img), "--out",
                        str(tmp_path / "out.glb")])
    assert rc == 2


def test_pick_backend_auto_picks_triposr_first(monkeypatch):
    _set_available(monkeypatch, triposr=True, trellis2=True, hunyuan3d=True)
    assert Img2Mesh.pick_backend("auto") == "triposr"


def test_pick_backend_auto_falls_through(monkeypatch):
    _set_available(monkeypatch, triposr=False, trellis2=True, hunyuan3d=True)
    assert Img2Mesh.pick_backend("auto") == "trellis2"
    _set_available(monkeypatch, triposr=False, trellis2=False, hunyuan3d=True)
    assert Img2Mesh.pick_backend("auto") == "hunyuan3d"


def test_explicit_unavailable_backend_returns_2(monkeypatch, tmp_path):
    _set_available(monkeypatch, triposr=False, trellis2=False, hunyuan3d=False)
    img = tmp_path / "in.png"
    img.write_bytes(b"x")
    rc = Img2Mesh.main(["--image", str(img), "--out",
                        str(tmp_path / "out.glb"), "--backend", "triposr"])
    assert rc == 2


def test_trellis2_not_implemented_message(monkeypatch, tmp_path):
    _set_available(monkeypatch, triposr=False, trellis2=True, hunyuan3d=False)
    img = tmp_path / "in.png"
    img.write_bytes(b"x")
    rc = Img2Mesh.main(["--image", str(img), "--out",
                        str(tmp_path / "out.glb"), "--backend", "trellis2"])
    assert rc == 3
    with pytest.raises(Img2Mesh.BackendNotImplementedError,
                       match="--backend triposr"):
        Img2Mesh.run_trellis2("a.png", "b.glb", {})


# ---------------------------------------------------------------------------
# Failure classification (torchmcubes landmine)
# ---------------------------------------------------------------------------

def test_classify_torchmcubes_import_failure():
    msg = Img2Mesh.classify_triposr_failure(
        1, "", "Traceback ...\nModuleNotFoundError: No module named "
               "'torchmcubes'")
    assert "torchmcubes" in msg
    assert "TORCHMCUBES_FALLBACK_PATCH" in msg


def test_classify_generic_failure_keeps_tail():
    msg = Img2Mesh.classify_triposr_failure(1, "", "CUDA out of memory")
    assert "CUDA out of memory" in msg


def test_classify_cuda_print_not_misdiagnosed_as_torchmcubes():
    # isosurface.py prints this line on runs where torchmcubes imported FINE;
    # a later OOM must not be blamed on a missing extension
    msg = Img2Mesh.classify_triposr_failure(
        1,
        "torchmcubes was not compiled with CUDA support, "
        "use CPU version instead.",
        "RuntimeError: CUDA out of memory")
    assert msg != Img2Mesh.TORCHMCUBES_ERROR
    assert "CUDA out of memory" in msg


def test_classify_dll_load_failure_is_torchmcubes():
    # the other Windows failure mode for a compiled ext: present but broken
    msg = Img2Mesh.classify_triposr_failure(
        1, "", "ImportError: DLL load failed while importing "
               "torchmcubes_module: The specified module could not be found.")
    assert msg == Img2Mesh.TORCHMCUBES_ERROR


def test_fallback_patch_constant_documents_both_shims():
    patch = Img2Mesh.TORCHMCUBES_FALLBACK_PATCH
    assert "mcubes" in patch
    assert "skimage" in patch
    assert "isosurface.py" in patch


# ---------------------------------------------------------------------------
# Output normalization (fake TripoSR output dir)
# ---------------------------------------------------------------------------

def test_normalize_output_obj_converted_to_glb(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    staging = tmp_path / "stage" / "0"
    staging.mkdir(parents=True)
    trimesh.creation.box(extents=(100.0, 60.0, 30.0)).export(
        staging / "mesh.obj")
    out = tmp_path / "final" / "purse.glb"
    result = Img2Mesh.normalize_output(tmp_path / "stage", out)
    assert result == out
    assert out.is_file() and out.stat().st_size > 0
    loaded = trimesh.load(out, force="mesh")
    assert len(loaded.vertices) > 0 and len(loaded.faces) > 0


def test_normalize_output_glb_copied(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    staging = tmp_path / "stage" / "0"
    staging.mkdir(parents=True)
    trimesh.creation.box(extents=(10.0, 10.0, 10.0)).export(
        staging / "mesh.glb")
    out = tmp_path / "out.glb"
    Img2Mesh.normalize_output(tmp_path / "stage", out)
    assert out.is_file()
    assert out.read_bytes() == (staging / "mesh.glb").read_bytes()


def test_normalize_output_empty_dir_raises(tmp_path):
    (tmp_path / "stage").mkdir()
    with pytest.raises(Img2Mesh.Img2MeshError):
        Img2Mesh.normalize_output(tmp_path / "stage", tmp_path / "out.glb")


# ---------------------------------------------------------------------------
# run_triposr glue (subprocess monkeypatched — no inference)
# ---------------------------------------------------------------------------

def _fake_run(write_mesh=None, returncode=0, stdout="", stderr=""):
    """Fake subprocess.run that drops a mesh into the --output-dir staging
    directory the way TripoSR does (<output_dir>/<i>/mesh.<fmt>)."""
    def run(cmd, **kwargs):
        staging = Path(cmd[cmd.index("--output-dir") + 1])
        if write_mesh is not None:
            sub = staging / "0"
            sub.mkdir(parents=True, exist_ok=True)
            write_mesh(sub)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
    return run


def test_run_triposr_success_normalizes_and_logs(monkeypatch, tmp_path):
    trimesh = pytest.importorskip("trimesh")
    monkeypatch.setattr(Img2Mesh.common, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        Img2Mesh.subprocess, "run",
        _fake_run(lambda d: trimesh.creation.box(
            extents=(10.0, 5.0, 3.0)).export(d / "mesh.obj")))
    out = tmp_path / "designs" / "purse.glb"
    rc = Img2Mesh.run_triposr(tmp_path / "in.png", out, {"mc_resolution": 32})
    assert rc == 0
    assert out.is_file() and out.stat().st_size > 0
    assert (tmp_path / "logs" / "img2mesh_triposr.log").is_file()


def test_run_triposr_torchmcubes_failure_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setattr(Img2Mesh.common, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        Img2Mesh.subprocess, "run",
        _fake_run(returncode=1,
                  stderr="ModuleNotFoundError: No module named 'torchmcubes'"))
    with pytest.raises(Img2Mesh.Img2MeshError) as exc:
        Img2Mesh.run_triposr(tmp_path / "in.png", tmp_path / "out.glb", {})
    assert exc.value.exit_code == 1
    assert "TORCHMCUBES_FALLBACK_PATCH" in str(exc.value)


def test_run_triposr_timeout_is_clean_error(monkeypatch, tmp_path):
    def raise_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
    monkeypatch.setattr(Img2Mesh.subprocess, "run", raise_timeout)
    # must surface as Img2MeshError (clean exit 1), not a raw TimeoutExpired
    with pytest.raises(Img2Mesh.Img2MeshError, match="timed out"):
        Img2Mesh.run_triposr(tmp_path / "in.png", tmp_path / "out.glb",
                             {"timeout_s": 5})
