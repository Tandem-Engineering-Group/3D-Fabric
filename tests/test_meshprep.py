"""Smoke tests for pipeline/MeshPrep.py.

Test 1 always runs (CLI --help + job JSON writer, no Blender needed).
The remaining tests run MeshPrep end-to-end (happy path, instanced glb,
.obj branch, failure path) and are skipped while Blender is absent.
Run from repo root:
  python -m pytest "tests/test_meshprep.py" -q
"""

import json
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pytest
import trimesh

from pipeline import MeshPrep, common

MESHPREP_CLI = REPO_ROOT / "pipeline" / "MeshPrep.py"

needs_blender = pytest.mark.skipif(not common.blender_available(),
                                   reason="Blender not installed (yet)")


def _force_shared_mesh(glb_path: Path) -> None:
    """Rewrite a glb in place so every node references mesh 0.

    trimesh exports duplicate geometry as separate glTF meshes; real-world
    instanced assets share one mesh across nodes, which Blender imports as
    multi-user datablocks. Patch the JSON chunk to reproduce that."""
    data = glb_path.read_bytes()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    for node in gltf["nodes"]:
        if "mesh" in node:
            node["mesh"] = 0
    payload = json.dumps(gltf, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)  # glb chunks are 4-aligned
    out = (data[:12] + struct.pack("<I", len(payload)) + b"JSON" + payload
           + data[20 + json_len:])
    out = out[:8] + struct.pack("<I", len(out)) + out[12:]  # total length
    glb_path.write_bytes(out)


@pytest.fixture
def sphere_glb(tmp_path):
    """~5k-tri icosphere built with trimesh, no Blender involved."""
    mesh = trimesh.creation.icosphere(subdivisions=4, radius=0.1)  # 5120 tris
    assert len(mesh.faces) > 4000
    path = tmp_path / "sphere.glb"
    mesh.export(str(path))
    assert path.stat().st_size > 0
    return path


def test_cli_help_and_job_writer(tmp_path, sphere_glb):
    proc = subprocess.run(
        [sys.executable, str(MESHPREP_CLI), "--help"],
        capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    for flag in ("--mesh", "--out", "--target-tris", "--merge-dist", "--stats"):
        assert flag in proc.stdout

    out = tmp_path / "clean.glb"
    stats = tmp_path / "meshstats.json"
    job = MeshPrep.build_job(sphere_glb, out, target_tris=500,
                             merge_dist=0.0005, stats=stats)
    job_path = MeshPrep.write_job(job, tmp_path / "job.json")
    assert job_path.is_file()

    doc = json.loads(job_path.read_text(encoding="utf-8"))
    assert doc["schema"] == "3dfabric.meshprep.job/1"
    assert Path(doc["mesh"]) == sphere_glb.resolve()
    assert Path(doc["out"]) == out.resolve()
    assert Path(doc["stats"]) == stats.resolve()
    assert doc["target_tris"] == 500
    assert doc["merge_dist"] == pytest.approx(0.0005)
    assert doc["draft"].startswith("DRAFT")

    # temp-file default location also works
    tmp_job = MeshPrep.write_job(job)
    try:
        assert json.loads(tmp_job.read_text(encoding="utf-8")) == doc
    finally:
        tmp_job.unlink()

    with pytest.raises(ValueError):
        MeshPrep.build_job(tmp_path / "bad.stl", out, 500, 0.0005, stats)
    with pytest.raises(ValueError):
        MeshPrep.build_job(sphere_glb, out, 0, 0.0005, stats)


@needs_blender
def test_meshprep_end_to_end(tmp_path, sphere_glb):
    out = tmp_path / "clean.glb"
    stats = MeshPrep.run(mesh=sphere_glb, out=out, target_tris=500)

    assert out.is_file()
    loaded = trimesh.load(str(out))
    geoms = (list(loaded.geometry.values())
             if isinstance(loaded, trimesh.Scene) else [loaded])
    loaded_tris = sum(len(g.faces) for g in geoms)
    assert loaded_tris > 0

    stats_path = MeshPrep.default_stats_path(out)
    assert stats_path.is_file()
    on_disk = json.loads(stats_path.read_text(encoding="utf-8"))
    assert on_disk == stats
    assert stats["schema"] == "3dfabric.meshstats/1"
    assert stats["objects"] >= 1
    assert stats["tris_before"] > 4000
    assert stats["tris_after"] <= 1000
    assert stats["tris_after"] >= 4  # still a real mesh, not collapsed
    assert stats["verts_after"] <= stats["verts_before"]
    assert stats["non_manifold_edges"] == 0  # icosphere is watertight
    assert len(stats["dims_m"]) == 3 and all(d > 0 for d in stats["dims_m"])
    assert stats["draft"].startswith("DRAFT")


@needs_blender
def test_meshprep_instanced_glb(tmp_path):
    """A glb where two nodes share ONE mesh (multi-user data in Blender).

    Regression: modifier_apply refuses multi-user datablocks, so decimation
    used to crash on instanced imports (e.g. a purse with two identical
    handles)."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.1)  # 1280 tris
    scene = trimesh.Scene()
    scene.add_geometry(mesh, geom_name="ico", node_name="a")
    offset = np.eye(4)
    offset[0, 3] = 0.3
    scene.add_geometry(mesh, geom_name="ico", node_name="b", transform=offset)
    src = tmp_path / "instanced.glb"
    scene.export(str(src))
    _force_shared_mesh(src)

    out = tmp_path / "instanced_clean.glb"
    stats = MeshPrep.run(mesh=src, out=out, target_tris=500)

    assert out.is_file()
    assert stats["objects"] == 2
    assert stats["tris_before"] > 2000  # both instances counted (2 x 1280)
    assert 4 <= stats["tris_after"] <= 1000
    # both instances survive with their transforms: spheres 0.3 m apart
    assert stats["dims_m"][0] > 0.4
    loaded = trimesh.load(str(out))
    geoms = (list(loaded.geometry.values())
             if isinstance(loaded, trimesh.Scene) else [loaded])
    assert sum(len(g.faces) for g in geoms) > 0


@needs_blender
def test_meshprep_obj_branch_default_paths(tmp_path):
    """.obj import branch, plus the default --out/--stats path chain."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.1)
    src = tmp_path / "sphere.obj"
    mesh.export(str(src))

    stats = MeshPrep.run(mesh=src, target_tris=500)

    out = MeshPrep.default_out_path(src)
    assert out == tmp_path / "sphere_clean.glb"
    assert out.is_file()
    assert MeshPrep.default_stats_path(out).is_file()
    assert stats["schema"] == "3dfabric.meshstats/1"
    assert stats["tris_before"] > 1000
    assert 4 <= stats["tris_after"] <= 1000


@needs_blender
def test_meshprep_failure_exits_nonzero(tmp_path):
    """Garbage input must surface as a raised error (Blender exit nonzero),
    never a silent success — exercises the os._exit(1) path in the worker."""
    bad = tmp_path / "bad.glb"
    bad.write_bytes(b"this is definitely not a glb")
    out = tmp_path / "never.glb"
    with pytest.raises(RuntimeError):
        MeshPrep.run(mesh=bad, out=out, target_tris=500)
    assert not out.exists()
