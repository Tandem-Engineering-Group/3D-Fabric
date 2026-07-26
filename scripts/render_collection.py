"""Render every concept in a collection manifest — runs INSIDE Blender:

  blender --background --python-exit-code 1 --python scripts/render_collection.py -- \
      --manifest designs/collection01.json --render-dir designs/renders/collection \
      --glb-dir designs/collection [--samples 128]

Per concept: rebuild the parametric bag with that concept's dimensions,
body/trim leathers, and hardware finish; render a still; export a cloth-only
glb so the pattern pipeline can cost it. One Blender session for the lot.
"""
import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_shoulder_bag as msb  # noqa: E402

HARDWARE = {
    "gold": ((0.85, 0.62, 0.25), 0.18),
    "silver": ((0.85, 0.87, 0.90), 0.12),
    "graphite": ((0.16, 0.16, 0.18), 0.30),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--render-dir", required=True)
    ap.add_argument("--glb-dir", required=True)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--only", help="comma-separated slugs to rebuild (default all)")
    return ap.parse_args(argv)


def hardware_material(kind):
    rgb, rough = HARDWARE[kind]
    mat = bpy.data.materials.new(f"HW_{kind}")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    return mat


def render_concept(c, args):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.curves):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    ns = SimpleNamespace(width_mm=float(c["w"]), height_mm=float(c["h"]),
                         depth_mm=float(c["d"]), strap_width_mm=float(c["strap"]),
                         crossbody_mm=1100.0, samples=args.samples)
    mat_body = msb.leather_material(f"Body_{c['slug']}", tuple(c["body"]),
                                    grain_scale=float(c["grain"]), rough=0.40)
    mat_trim = msb.leather_material(f"Trim_{c['slug']}", tuple(c["trim"]),
                                    grain_scale=800.0, rough=0.36)
    mat_hw = hardware_material(c["hw"])
    mat_floor = msb.flat_material("Sweep", (0.80, 0.78, 0.75), rough=0.9)

    body = msb.build_body(ns, mat_body, mat_trim)
    strap = msb.build_shoulder_strap(ns, mat_trim)
    msb.build_crossbody(ns, mat_trim)
    msb.build_hardware(ns, mat_hw, mat_trim)
    msb.build_cyclorama(ns, mat_floor)
    msb.setup_render(ns)

    cam = bpy.context.scene.camera
    f = float(c.get("cam", 1.0))
    cam.location = tuple(v * f for v in cam.location)

    render_dir = Path(args.render_dir)
    render_dir.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(render_dir / f"{c['slug']}_raw.png")
    bpy.ops.render.render(write_still=True)

    for obj in (body, strap):
        for mod in list(obj.modifiers):
            obj.modifiers.remove(mod)
        for p in obj.data.polygons:
            p.use_smooth = False
    glb_dir = Path(args.glb_dir)
    glb_dir.mkdir(parents=True, exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o.type == "MESH" and o.name in
                     ("CrescentBody", "ShoulderStrap", "CrossbodyStrap"))
    bpy.ops.export_scene.gltf(filepath=str(glb_dir / f"{c['slug']}.glb"),
                              use_selection=True)
    print(f"[collection] {c['slug']} rendered + exported", flush=True)


def main():
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    concepts = manifest["concepts"]
    if args.only:
        keep = set(args.only.split(","))
        concepts = [c for c in concepts if c["slug"] in keep]
    for c in concepts:
        render_concept(c, args)
    print(f"[collection] done: {len(concepts)} concepts")


main()
