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


def ensure_seams(obj):
    """The addon errors on seamless meshes. Auto-seam fallback: Smart UV
    Project islands -> island borders become seams. Works on any mesh."""
    import math
    if any(e.use_seam for e in obj.data.edges):
        return "existing"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.uv.seams_from_islands()
    bpy.ops.object.mode_set(mode="OBJECT")
    n = sum(1 for e in obj.data.edges if e.use_seam)
    return f"auto ({n} edges)"


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
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
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

    Path(job["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    log("report:", json.dumps({k: v for k, v in report.items() if k != 'errors'}),
        f"errors={len(report['errors'])}")
    if not report["svgs"]:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)  # Blender exits 0 on script exceptions; force real failure


main()
