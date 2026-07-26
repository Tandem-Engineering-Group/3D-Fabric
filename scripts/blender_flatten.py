"""Runs INSIDE Blender: unfold a mesh into raw sewing-pattern SVG(s).

  blender --background --python scripts/blender_flatten.py -- <job.json>

Job JSON: {"mesh": path, "raw_dir": dir, "unwrap": "ANGLE_BASED", "target_tris": 5000,
           "seams": path-or-null, "report": path}
seams file: {"<object_name>": [[v_idx, v_idx], ...], ...} — edges to mark as seams.
Per mesh object: mark seams -> object.seams_to_sewingpattern -> export_sewingpattern
to raw_<i>.svg. Report JSON lists produced SVGs; exits nonzero if none succeeded
(Blender swallows script exceptions, so failure is signaled explicitly).
"""
import json
import os
import sys
import traceback
from pathlib import Path

import addon_utils
import bmesh
import bpy


def log(*a):
    print("[flatten]", *a, flush=True)


def import_mesh(path: Path):
    ext = path.suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise ValueError(f"unsupported mesh format: {ext}")


def mark_seams(obj, edge_pairs):
    wanted = {frozenset(p) for p in edge_pairs}
    n = 0
    for e in obj.data.edges:
        if frozenset(e.vertices) in wanted:
            e.use_seam = True
            n += 1
    return n


def object_mode():
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError:
        pass


def weld_and_deflake(obj, weld_dist: float = 1e-5, min_area_frac: float = 0.002):
    """glTF splits vertices wherever normals differ, so imported meshes arrive
    as disconnected per-shading-island patches (an AI blob came in as 6.5k
    fragments). Weld position-coincident verts so real topology is visible to
    the seam logic, and drop tiny floater shells (marching-cubes noise)."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld_dist)

    seen, shells = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, shell = [f], []
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            shell.append(cur)
            for e in cur.edges:
                stack.extend(lf for lf in e.link_faces if lf.index not in seen)
        shells.append(shell)
    total_area = sum(f.calc_area() for f in bm.faces) or 1.0
    doomed = [f for shell in shells
              if sum(f.calc_area() for f in shell) < min_area_frac * total_area
              for f in shell]
    if doomed and len(doomed) < len(bm.faces):
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(me)
    me.update()
    bm.free()
    return (f"welded {before}->{len(me.vertices)} verts, "
            f"{len(shells)} shell(s), dropped {len(doomed)} floater faces")


def _pieces_if_cut(bm, seam_edges) -> int:
    """How many pieces the exporter would produce: connected face components
    treating seam edges (and boundaries) as cuts."""
    cut = set(seam_edges)
    seen = set()
    comps = 0
    for f in bm.faces:
        if f.index in seen:
            continue
        comps += 1
        stack = [f]
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            for e in cur.edges:
                if e in cut or len(e.link_faces) != 2:
                    continue
                stack.extend(lf for lf in e.link_faces if lf.index not in seen)
    return comps


def ensure_seams(obj, sharp_deg: float = 40.0, max_pieces: int = 24):
    """The addon errors on seamless meshes. Auto-seam strategy:

    Boundary edges are always safe to mark (they are already pattern borders
    and cut nothing). Interior sharp edges become seams at the lowest
    sharpness threshold (40->60->75 deg) whose resulting PIECE COUNT stays
    sewable (<= max_pieces) — on decimated marching-cubes meshes nearly every
    edge reads as "sharp" and lower thresholds dice the mesh into confetti.
    Failing all thresholds, coarse Smart-UV islands (89 deg) provide a few
    large panels for smooth/noisy closed blobs."""
    import math
    me = obj.data
    if any(e.use_seam for e in me.edges):
        return "existing"
    bm = bmesh.new()
    bm.from_mesh(me)
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    for deg in (sharp_deg, 60.0, 75.0):
        sharp = [e for e in bm.edges if len(e.link_faces) == 2
                 and e.calc_face_angle(0.0) > math.radians(deg)]
        if not sharp and not boundary:
            break  # closed smooth mesh: nothing to mark at any threshold
        n_pieces = _pieces_if_cut(bm, sharp)
        if n_pieces <= max_pieces:
            for e in sharp + boundary:
                e.seam = True
            bm.to_mesh(me)
            me.update()
            bm.free()
            return (f"auto-bmesh ({len(sharp)} sharp @{deg:.0f}deg + "
                    f"{len(boundary)} boundary -> {n_pieces} pieces)")
    bm.free()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(89), island_margin=0.03)
    bpy.ops.uv.seams_from_islands()
    bpy.ops.object.mode_set(mode="OBJECT")
    n = sum(1 for e in me.edges if e.use_seam)
    return f"auto-islands ({n} edges)"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    job = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    raw_dir = Path(job["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    report = {"svgs": [], "objects": [], "errors": []}

    addon_utils.enable("seams_to_sewing_pattern", default_set=False)

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    import_mesh(Path(job["mesh"]))

    seams = {}
    if job.get("seams"):
        seams = json.loads(Path(job["seams"]).read_text(encoding="utf-8"))

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    # largest first so piece-1 is the main body, stable ordering for labels
    meshes.sort(key=lambda o: -(o.dimensions.x * o.dimensions.y + o.dimensions.z))

    for i, obj in enumerate(meshes, start=1):
        try:
            object_mode()  # a failed op can strand us in EDIT mode
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            log(f"{obj.name}: {weld_and_deflake(obj)}")
            if obj.name in seams:
                log(f"{obj.name}: marked {mark_seams(obj, seams[obj.name])} seam edges")
            log(f"{obj.name}: seams = {ensure_seams(obj)}")

            bpy.ops.object.seams_to_sewingpattern(
                "EXEC_DEFAULT",
                do_unwrap=job.get("unwrap", "ANGLE_BASED"),
                keep_original=False,
                use_remesh=True,
                apply_modifiers=True,
                target_tris=int(job.get("target_tris", 5000)),
            )
            # operator replaces the object; re-fetch active for the export
            flat = bpy.context.view_layer.objects.active
            svg_path = raw_dir / f"raw_{i}.svg"
            bpy.ops.object.export_sewingpattern(
                "EXEC_DEFAULT",
                filepath=str(svg_path),
                alignment_markers="AUTO",
                file_format="SVG",
            )
            if svg_path.is_file() and svg_path.stat().st_size > 0:
                report["svgs"].append(str(svg_path))
                report["objects"].append(obj.name)
                log(f"{obj.name}: exported {svg_path.name}")
            else:
                report["errors"].append(f"{obj.name}: export produced no file")
        except Exception:
            report["errors"].append(f"{obj.name}:\n{traceback.format_exc()}")
            log(f"{obj.name}: FAILED")
            object_mode()

    Path(job["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    log("report:", json.dumps({k: v for k, v in report.items() if k != 'errors'}),
        f"errors={len(report['errors'])}")
    if not report["svgs"]:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)  # Blender exits 0 on script exceptions; force real failure


main()
