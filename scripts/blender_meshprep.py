"""Blender-side worker for pipeline/MeshPrep.py. Runs INSIDE Blender:

  blender --background --python scripts/blender_meshprep.py -- <job.json>

The job JSON (schema 3dfabric.meshprep.job/1) carries mesh/out/stats paths
and params. This script wipes the default scene, imports the mesh, cleans
every mesh object (merge by distance, recalc outward normals, count
non-manifold edges), decimates to the triangle budget, exports a .glb and
writes the meshstats JSON. Any failure exits nonzero so run_blender raises.
"""

import json
import os
import sys
import traceback


def job_path_from_argv(argv):
    if "--" not in argv:
        raise ValueError("expected: blender --background --python "
                         "blender_meshprep.py -- <job.json>")
    rest = argv[argv.index("--") + 1:]
    if not rest:
        raise ValueError("missing job json path after '--'")
    return rest[0]


def total_tris(meshes):
    n = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        n += len(obj.data.loop_triangles)
    return n


def main():
    import bpy
    import bmesh
    from mathutils import Vector

    with open(job_path_from_argv(sys.argv), encoding="utf-8") as f:
        job = json.load(f)
    if job.get("schema") != "3dfabric.meshprep.job/1":
        raise ValueError("job file is not a 3dfabric.meshprep.job/1 document")
    src = job["mesh"]
    out = job["out"]
    stats_path = job["stats"]
    target_tris = int(job["target_tris"])
    merge_dist = float(job["merge_dist"])
    if not os.path.isfile(src):
        raise FileNotFoundError(f"input mesh not found: {src}")

    # Fresh empty scene: no default cube/camera/light polluting the export.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    ext = os.path.splitext(src)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=src)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=src)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=src)
    else:
        raise ValueError(f"unsupported mesh extension: {ext}")

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"no mesh objects imported from {src}")

    # Instanced imports (one mesh datablock shared by several objects) break
    # modifier_apply ("Modifiers cannot be applied to multi-user data") and
    # would run the edit-mode cleanup twice on the same data. Give every
    # object its own copy before touching anything.
    for obj in meshes:
        if obj.data.users > 1:
            obj.data = obj.data.copy()

    verts_before = sum(len(o.data.vertices) for o in meshes)
    tris_before = total_tris(meshes)

    non_manifold = 0
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=merge_dist)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.select_non_manifold()
        bm = bmesh.from_edit_mesh(obj.data)
        non_manifold += sum(1 for e in bm.edges if e.select)
        bpy.ops.object.mode_set(mode="OBJECT")

    current = total_tris(meshes)
    if current > target_tris:
        # One shared ratio keeps relative detail balanced across objects.
        ratio = max(target_tris / current, 0.05)
        for obj in meshes:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            mod = obj.modifiers.new(name="MeshPrepDecimate", type="DECIMATE")
            mod.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.context.view_layer.update()
    verts_after = sum(len(o.data.vertices) for o in meshes)
    tris_after = total_tris(meshes)

    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], wc[i])
                maxs[i] = max(maxs[i], wc[i])
    dims_m = [maxs[i] - mins[i] for i in range(3)]

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
    if not os.path.isfile(out):
        raise RuntimeError(f"glb export produced no file: {out}")

    stats = {
        "schema": "3dfabric.meshstats/1",
        "source": src,
        "output": out,
        "objects": len(meshes),
        "verts_before": verts_before,
        "verts_after": verts_after,
        "tris_before": tris_before,
        "tris_after": tris_after,
        "non_manifold_edges": non_manifold,
        "dims_m": dims_m,
        "draft": job.get("draft", "DRAFT — unverified mesh stats"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(stats_path)), exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"blender_meshprep: wrote {out} and {stats_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        # Blender swallows script exceptions and exits 0 unless
        # --python-exit-code is set; force a real nonzero exit instead.
        os._exit(1)
