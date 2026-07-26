"""Parametric curved-bottom shoulder bag ("Crescent") v2 — runs INSIDE Blender:

  blender --background --python scripts/make_shoulder_bag.py -- \
      --out designs/CrescentDemo.glb --render-dir designs/renders \
      --json-report logs/crescent_report.json

Original silhouette study (no third-party branding). v2 upgrades the hero
render to product-photo quality: Cycles GPU, pebbled-leather shader with
per-colorway variants, beveled soft body, top zipper + gold slider, chain-end
shoulder strap with D-rings, studio cyclorama + 3-point lighting.

Only CLOTH objects (body, straps) go into the exported glb for the pattern
pipeline; hardware (chain, rings, zipper) is render-only and prefixed HW_.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Vector

M = 0.001  # mm -> meters

COLORWAYS = {
    "brown":  (0.085, 0.042, 0.024),
    "black":  (0.020, 0.018, 0.017),
    "cognac": (0.320, 0.150, 0.060),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--width-mm", type=float, default=290.0)
    ap.add_argument("--height-mm", type=float, default=170.0)
    ap.add_argument("--depth-mm", type=float, default=75.0)
    ap.add_argument("--strap-width-mm", type=float, default=20.0)
    ap.add_argument("--crossbody-mm", type=float, default=1100.0)
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render-dir", default=None)
    ap.add_argument("--hero", default=None, help="also copy the brown render here")
    ap.add_argument("--json-report", default=None)
    return ap.parse_args(argv)


# ---------------------------------------------------------------- geometry

def profile_points(w, h):
    hw = w / 2.0
    top_z, peak_z = 0.42 * h, 0.52 * h
    side_z = 0.12 * h
    rz = 0.68 * h
    pts = [(hw * 0.965, top_z), (hw, side_z)]
    for i in range(1, 25):
        th = math.pi * i / 25.0
        pts.append((hw * math.cos(th), side_z - rz * math.sin(th) * 0.58))
    pts.append((-hw, side_z))
    pts.append((-hw * 0.965, top_z))
    for i in range(1, 12):
        t = i / 12.0
        x = -hw * 0.965 + t * (2 * hw * 0.965)
        pts.append((x, top_z + (peak_z - top_z) * math.sin(math.pi * t)))
    return pts


def top_arc(w, h, t):
    """Point on the top arc (zipper line), t in 0..1, mm coords (x, z)."""
    hw = w / 2.0
    top_z, peak_z = 0.42 * h, 0.52 * h
    x = -hw * 0.94 + t * (2 * hw * 0.94)
    return x, top_z + (peak_z - top_z) * math.sin(math.pi * t)


def strap_arc(w, h, t, apex=0.095):
    hw = w / 2.0 * M
    top = 0.42 * h * M
    span = hw * 0.62
    return Vector((-span + 2 * span * t, 0.0, top + apex * math.sin(math.pi * t)))


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
    nv = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, 2 * d, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.material_index = 0 if abs(f.normal.y) > 0.5 else 1
    obj = new_object("CrescentBody", bm, [mat_body, mat_trim])
    bev = obj.modifiers.new("SoftEdge", "BEVEL")   # render-only puffiness
    bev.width = 0.009
    bev.segments = 4
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(40)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def build_shoulder_strap(a, mat):
    """Leather section only spans t 0.17..0.83 — chain covers the ends."""
    wy = a.strap_width_mm * M / 2
    bm = bmesh.new()
    prev = None
    for i in range(25):
        t = 0.17 + (0.83 - 0.17) * i / 24.0
        p = strap_arc(a.width_mm, a.height_mm, t)
        v1 = bm.verts.new((p.x, -wy, p.z))
        v2 = bm.verts.new((p.x, wy, p.z))
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = new_object("ShoulderStrap", bm, [mat])
    sol = obj.modifiers.new("Thickness", "SOLIDIFY")   # render-only
    sol.thickness = 0.003
    sol.offset = 0.0
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def build_crossbody(a, mat):
    L = a.crossbody_mm * M
    w = a.strap_width_mm * 0.9 * M
    z = (0.12 - 0.68 * 0.58) * a.height_mm * M
    bm = bmesh.new()
    prev = None
    for i in range(23):
        x = -L / 2 + L * i / 22
        v1 = bm.verts.new((x, 0.30, z))
        v2 = bm.verts.new((x, 0.30 + w, z))
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = new_object("CrossbodyStrap", bm, [mat])
    obj.hide_render = True
    return obj


def add_torus(name, loc, rot, major, minor, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=28, minor_segments=12,
                                     location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rot
    obj.scale = scale
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def build_hardware(a, mat_gold, mat_trim):
    """Chain ends + D-rings on the strap, zipper line + slider on the body."""
    w, h = a.width_mm, a.height_mm
    # D-rings at the strap anchors
    for t_end in (0.0, 1.0):
        p = strap_arc(w, h, t_end)
        add_torus("HW_Ring", (p.x, 0, p.z - 0.004), Euler((math.pi / 2, 0, 0)),
                  0.011, 0.0022, mat_gold)
    # chain links along the strap ends
    for t0, t1 in ((0.015, 0.165), (0.835, 0.985)):
        n = 7
        for i in range(n):
            t = t0 + (t1 - t0) * i / (n - 1)
            p = strap_arc(w, h, t)
            p2 = strap_arc(w, h, t + 0.01)
            pitch = math.atan2(p2.z - p.z, p2.x - p.x)
            rx = math.pi / 2 if i % 2 == 0 else 0.0
            add_torus("HW_Link", p, Euler((rx, -pitch, 0), "ZYX"),
                      0.0085, 0.0017, mat_gold, scale=(1.35, 1.0, 0.8))
    # zipper: a slim tube along the top arc, slightly proud of the body
    curve = bpy.data.curves.new("HW_ZipCurve", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0016
    curve.bevel_resolution = 4
    sp = curve.splines.new("POLY")
    pts = [top_arc(w, h, i / 30.0) for i in range(31)]
    sp.points.add(len(pts) - 1)
    for k, (x, z) in enumerate(pts):
        sp.points[k].co = (x * M, 0.0, z * M + 0.0012, 1.0)
    zc = bpy.data.objects.new("HW_Zipper", curve)
    zc.data.materials.append(mat_trim)
    bpy.context.collection.objects.link(zc)
    # slider + pull at 30% along the zip
    sx, sz = top_arc(w, h, 0.30)
    bpy.ops.mesh.primitive_cube_add(location=(sx * M, 0, sz * M + 0.0022))
    slider = bpy.context.active_object
    slider.name = "HW_Slider"
    slider.scale = (0.006, 0.0035, 0.0028)
    slider.data.materials.append(mat_gold)
    add_torus("HW_Pull", (sx * M + 0.004, 0, sz * M - 0.004),
              Euler((0, math.pi / 5, 0)), 0.006, 0.0012, mat_gold,
              scale=(1.0, 0.7, 1.4))


def build_cyclorama(a, mat):
    """Seamless studio sweep: floor, curved bend, vertical back wall."""
    gz = (0.12 - 0.68 * 0.58) * a.height_mm * M - 0.0005
    r = 0.45
    prof = [(-1.8, gz)]
    for i in range(13):
        th = math.radians(90 * i / 12)
        prof.append((0.35 - r + r * math.sin(th), gz + r - r * math.cos(th)))
    prof.append((0.35, gz + 1.5))
    bm = bmesh.new()
    xw = 2.4
    prev = None
    for y, z in prof:
        v1 = bm.verts.new((-xw, y, z))
        v2 = bm.verts.new((xw, y, z))
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = new_object("Cyclorama", bm, [mat])
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


# ---------------------------------------------------------------- materials

def leather_material(name, rgb, grain_scale=550.0, rough=0.38):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    try:
        bsdf.inputs["Sheen Weight"].default_value = 0.12
    except KeyError:
        pass
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = grain_scale
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.0008
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.35
    ramp.inputs["From Max"].default_value = 0.65
    ramp.inputs["To Min"].default_value = rough - 0.07
    ramp.inputs["To Max"].default_value = rough + 0.07
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])
    return mat


def gold_material():
    mat = bpy.data.materials.new("Gold")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.85, 0.62, 0.25, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.18
    return mat


def flat_material(name, rgb, rough=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    return mat


# ---------------------------------------------------------------- scene

def setup_render(a):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dtype in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = dtype
                prefs.get_devices()
                for dev in prefs.devices:
                    dev.use = dev.type != "CPU"
                scene.cycles.device = "GPU"
                print(f"[crescent] cycles on GPU via {dtype}")
                break
            except Exception:
                continue
    except Exception as e:
        print(f"[crescent] GPU setup failed, CPU fallback: {e}")
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1150
    scene.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.34, 0.33, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.05
    scene.world = world

    def area(name, loc, rot, power, size):
        li = bpy.data.lights.new(name, "AREA")
        li.energy = power
        li.size = size
        ob = bpy.data.objects.new(name, li)
        ob.location = loc
        ob.rotation_euler = Euler(tuple(math.radians(v) for v in rot))
        bpy.context.collection.objects.link(ob)

    area("Key", (0.45, -0.75, 0.55), (55, 0, 28), 18, 0.9)
    area("Fill", (-0.60, -0.60, 0.30), (65, 0, -40), 5, 0.7)
    area("Rim", (-0.15, 0.55, 0.70), (-125, 0, -15), 14, 0.6)
    print("[crescent] view transform:", scene.view_settings.view_transform,
          "| exposure:", scene.view_settings.exposure)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 55
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 0.74
    cam_data.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0.46, -0.60, 0.18)
    cam.rotation_euler = Euler((math.radians(79), 0, math.radians(37.5)))
    bpy.context.collection.objects.link(cam)
    scene.camera = cam


def main():
    a = parse_args()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    mat_trim = leather_material("TrimLeather", (0.014, 0.012, 0.011),
                                grain_scale=800.0, rough=0.34)
    mat_gold = gold_material()
    mat_body = leather_material("BodyLeather", COLORWAYS["brown"])
    mat_floor = flat_material("Sweep", (0.80, 0.78, 0.75), rough=0.9)

    body = build_body(a, mat_body, mat_trim)
    strap = build_shoulder_strap(a, mat_trim)
    cross = build_crossbody(a, mat_trim)
    build_hardware(a, mat_gold, mat_trim)
    build_cyclorama(a, mat_floor)

    if a.render_dir:
        setup_render(a)
        out_dir = Path(a.render_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        bsdf = mat_body.node_tree.nodes["Principled BSDF"]
        for cname, rgb in COLORWAYS.items():
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
            bpy.context.scene.render.filepath = str(out_dir / f"CrescentDemo_{cname}.png")
            bpy.ops.render.render(write_still=True)
            print(f"[crescent] rendered {cname}")
        bsdf.inputs["Base Color"].default_value = (*COLORWAYS["brown"], 1.0)
        if a.hero:
            shutil.copyfile(out_dir / "CrescentDemo_brown.png", a.hero)

    # crisp cloth-only export for the pattern pipeline
    for obj in (body, strap):
        for mod in list(obj.modifiers):
            obj.modifiers.remove(mod)
        for p in obj.data.polygons:
            p.use_smooth = False
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o.type == "MESH" and o.name in
                     ("CrescentBody", "ShoulderStrap", "CrossbodyStrap"))
    bpy.ops.export_scene.gltf(filepath=str(a.out), use_selection=True)

    if a.json_report:
        Path(a.json_report).write_text(json.dumps(
            {"objects": 3, "colorways": list(COLORWAYS),
             "width_mm": a.width_mm, "height_mm": a.height_mm,
             "depth_mm": a.depth_mm}, indent=2), encoding="utf-8")
    print("[crescent] done")


if __name__ == "__main__":
    main()
