"""Parametric curved-bottom shoulder bag ("Crescent") — runs INSIDE Blender:

  blender --background --python scripts/make_shoulder_bag.py -- \
      --out designs/CrescentDemo.glb --render designs/CrescentDemo.png \
      --json-report logs/crescent_report.json

Original silhouette study (no third-party branding): crescent body extruded to
depth (caps = front/back panels, extrusion wall = gusset/zip band), arched
shoulder strap, flat crossbody strap. Cap<->band edges are ~90 deg so the
pipeline's auto-seam pass cuts exactly at panel boundaries. Deterministic.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--width-mm", type=float, default=290.0)
    ap.add_argument("--height-mm", type=float, default=170.0)   # corner-to-bottom span
    ap.add_argument("--depth-mm", type=float, default=75.0)
    ap.add_argument("--strap-width-mm", type=float, default=20.0)
    ap.add_argument("--crossbody-mm", type=float, default=1100.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render", default=None)
    ap.add_argument("--json-report", default=None)
    return ap.parse_args(argv)


M = 0.001  # mm -> meters


def profile_points(w, h):
    """Closed CCW profile in the XZ plane, mm. Top corners at z=+0.42h,
    shallow top arc peaking +0.52h, elliptic crescent bottom to -0.56h."""
    hw = w / 2.0
    top_z, peak_z = 0.42 * h, 0.52 * h
    side_z = 0.12 * h            # where the straight side meets the bottom ellipse
    rz = side_z + 0.56 * h       # ellipse vertical radius
    pts = [(hw * 0.965, top_z)]
    pts.append((hw, side_z))
    for i in range(1, 25):       # bottom ellipse, right -> left (shallow crescent)
        th = math.pi * i / 25.0
        pts.append((hw * math.cos(th), side_z - rz * math.sin(th) * 0.58))
    pts.append((-hw, side_z))
    pts.append((-hw * 0.965, top_z))
    for i in range(1, 12):       # top arc, left -> right
        t = i / 12.0
        x = -hw * 0.965 + t * (2 * hw * 0.965)
        pts.append((x, top_z + (peak_z - top_z) * math.sin(math.pi * t)))
    return pts


def make_material(name, rgb, rough):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def new_object(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def build_body(a, mat_body, mat_trim):
    prof = profile_points(a.width_mm, a.height_mm)
    d = a.depth_mm * M / 2
    bm = bmesh.new()
    verts = [bm.verts.new((x * M, -d, z * M)) for x, z in prof]
    face = bm.faces.new(verts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0, 2 * d, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.material_index = 0 if abs(f.normal.y) > 0.5 else 1  # caps brown, band black
    return new_object("CrescentBody", bm, [mat_body, mat_trim])


def build_shoulder_strap(a, mat):
    """Arched strip from top corner to top corner."""
    hw = a.width_mm / 2 * M
    top = 0.42 * a.height_mm * M
    span = hw * 0.62
    apex = 0.095                          # meters above attachment
    wy = a.strap_width_mm * M / 2
    bm = bmesh.new()
    prev = None
    for i in range(25):
        t = i / 24.0
        x = -span + 2 * span * t
        z = top + apex * math.sin(math.pi * t)
        v1 = bm.verts.new((x, -wy, z))
        v2 = bm.verts.new((x, wy, z))
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_object("ShoulderStrap", bm, [mat])


def build_crossbody(a, mat):
    """Flat strip on the ground behind the bag (mostly out of frame, but it
    must exist so the pattern includes its cut)."""
    L = a.crossbody_mm * M
    w = a.strap_width_mm * 0.9 * M
    z = -(0.12 + 0.56 * 0.82) * a.height_mm * M  # ground level-ish
    y0 = a.depth_mm * M
    bm = bmesh.new()
    n = 22
    prev = None
    for i in range(n + 1):
        x = -L / 2 + L * i / n
        v1 = bm.verts.new((x, y0, z))
        v2 = bm.verts.new((x, y0 + w, z))
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = new_object("CrossbodyStrap", bm, [mat])
    obj.hide_render = True   # in the pattern/export, not in the hero shot
    return obj


def setup_scene_and_render(a, body, render_path):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.83, 0.80, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    scene.world = world
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -0.6

    # exact profile bottom: side_z - rz*0.58 with side_z=0.12h, rz=0.68h
    ground_z = (0.12 - 0.68 * 0.58) * a.height_mm * M - 0.0005
    bm = bmesh.new()
    s = 8.0
    vs = [bm.verts.new(p) for p in
          ((-s, -s, ground_z), (s, -s, ground_z), (s, s, ground_z), (-s, s, ground_z))]
    bm.faces.new(vs)
    ground = new_object("Ground", bm, [make_material("GroundMat", (0.82, 0.79, 0.76), 0.9)])

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 1.8
    sun.rotation_euler = (math.radians(50), math.radians(-15), math.radians(35))
    bpy.context.collection.objects.link(sun)
    area = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "AREA"))
    area.data.energy = 25.0
    area.data.size = 1.2
    area.location = (0.35, -0.55, 0.55)
    area.rotation_euler = (math.radians(55), 0, math.radians(30))
    bpy.context.collection.objects.link(area)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = (0.36, -0.48, 0.13)
    cam.rotation_euler = (math.radians(78), 0, math.radians(37))
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    # soften the hero object for the render only
    bev = body.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.004
    bev.segments = 2
    for p in body.data.polygons:
        p.use_smooth = True

    engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = ("BLENDER_EEVEE" if "BLENDER_EEVEE" in engines
                           else "BLENDER_EEVEE_NEXT")
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 900
    scene.render.filepath = str(render_path)
    bpy.ops.render.render(write_still=True)

    body.modifiers.remove(bev)      # crisp geometry for the pattern export
    for p in body.data.polygons:
        p.use_smooth = False
    bpy.data.objects.remove(ground, do_unlink=True)


def main():
    a = parse_args()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    mat_body = make_material("BodyBrown", (0.11, 0.055, 0.032), 0.55)
    mat_trim = make_material("TrimBlack", (0.015, 0.013, 0.012), 0.4)
    body = build_body(a, mat_body, mat_trim)
    build_shoulder_strap(a, mat_trim)
    build_crossbody(a, mat_trim)

    if a.render:
        Path(a.render).parent.mkdir(parents=True, exist_ok=True)
        setup_scene_and_render(a, body, a.render)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o.type == "MESH" and o.name != "Ground")
    bpy.ops.export_scene.gltf(filepath=str(a.out), use_selection=True)

    if a.json_report:
        tris = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")
        Path(a.json_report).write_text(json.dumps(
            {"objects": sum(1 for o in bpy.data.objects if o.type == "MESH"),
             "faces": tris, "width_mm": a.width_mm, "height_mm": a.height_mm,
             "depth_mm": a.depth_mm}, indent=2), encoding="utf-8")
    print("[crescent] done")


main()
