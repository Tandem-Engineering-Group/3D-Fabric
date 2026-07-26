"""Parametric demo tote for the 3D-Fabric pipeline — runs INSIDE Blender headless.

Builds an open-box tote body (front/back panels, two side gussets, bottom, no
top face) plus two flat strap strips, grid-subdivided to ~--quad-mm quads so
downstream unwrap/remesh has density. Every edge where two body panels meet is
marked as a UV seam (the 4 vertical corner lines + the 4 bottom-perimeter
lines); the open top rim is a natural pattern boundary. Straps are separate
flat rectangles whose outline IS their boundary — no seams needed. Exports all
objects to a GLB, renders an 800x800 3/4-view PNG (EEVEE, CPU-Cycles
fallback), and optionally writes a JSON verification report:
    {"objects": N, "seam_edges": N, "tris": N}

CLI (Blender hands the script everything after "--"; quote paths — the repo
path contains spaces):
  "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" --background
      --python "scripts/make_tote.py" --
      --width-mm 350 --height-mm 320 --depth-mm 120
      --strap-length-mm 550 --strap-width-mm 30 --quad-mm 20
      --out "designs/FeltCheckTote.glb" --render "designs/FeltCheckTote.png"
      --json-report "designs/FeltCheckTote_report.json"

Outside Blender the module imports/compiles cleanly and `--help` works;
running the build without bpy exits with code 2. Deterministic: no randomness,
identical inputs produce identical meshes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from pathlib import Path

MM = 0.001  # Blender scene unit is meters; pipeline params are mm

BODY_COLOR = (0.72, 0.16, 0.14, 1.0)   # muted felt red
STRAP_COLOR = (0.16, 0.11, 0.07, 1.0)  # dark leather brown
STRAP_LIFT_MM = 40.0                   # straps float this far above the rim
# Shared panel borders are computed with identical FP expressions, so they
# weld at essentially zero distance; junction test tolerance is 0.1 mm,
# far below any sane --quad-mm.
WELD_DIST = 1e-6
JUNCTION_EPS = 1e-4


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args. Inside Blender, only argv after the '--' separator."""
    if argv is None:
        argv = sys.argv
        argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    p = argparse.ArgumentParser(
        prog="make_tote.py",
        description="Build a parametric demo tote (open box + two straps) "
                    "inside headless Blender; export GLB + render PNG.")
    p.add_argument("--width-mm", type=float, default=350.0,
                   help="body width, front/back panel span (default 350)")
    p.add_argument("--height-mm", type=float, default=320.0,
                   help="body height, bottom to open rim (default 320)")
    p.add_argument("--depth-mm", type=float, default=120.0,
                   help="body depth, side gusset span (default 120)")
    p.add_argument("--strap-length-mm", type=float, default=550.0,
                   help="strap strip length (default 550)")
    p.add_argument("--strap-width-mm", type=float, default=30.0,
                   help="strap strip width (default 30)")
    p.add_argument("--quad-mm", type=float, default=20.0,
                   help="target quad size for grid subdivision (default 20)")
    p.add_argument("--out", default="designs/FeltCheckTote.glb",
                   help="output GLB path (default designs/FeltCheckTote.glb)")
    p.add_argument("--render", default="designs/FeltCheckTote.png",
                   help="output 800x800 PNG path "
                        "(default designs/FeltCheckTote.png)")
    p.add_argument("--json-report", default=None,
                   help="optional JSON report path: objects/seam_edges/tris")
    return p.parse_args(argv)


def _segments(length_mm: float, quad_mm: float) -> int:
    return max(1, round(length_mm / quad_mm))


def _grid(origin, u_axis, u_len, nu, v_axis, v_len, nv):
    """Planar quad grid: (verts, faces) with local 0-based indices.

    Coordinates use origin + axis * (length * i/n) so endpoints are exact and
    borders shared between panels produce bit-identical vertices for welding.
    """
    verts = []
    for j in range(nv + 1):
        fv = v_len * (j / nv)
        for i in range(nu + 1):
            fu = u_len * (i / nu)
            verts.append((origin[0] + u_axis[0] * fu + v_axis[0] * fv,
                          origin[1] + u_axis[1] * fu + v_axis[1] * fv,
                          origin[2] + u_axis[2] * fu + v_axis[2] * fv))
    faces = []
    for j in range(nv):
        row = j * (nu + 1)
        for i in range(nu):
            a = row + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    return verts, faces


def _is_panel_junction(p, q, hw: float, hd: float,
                       eps: float = JUNCTION_EPS) -> bool:
    """True if edge (p, q) lies on a line where two body panels meet.

    Junctions: 4 vertical corner columns (|x|=hw AND |y|=hd) and the bottom
    perimeter (z=0 AND |y|=hd for front/back, z=0 AND |x|=hw for the sides).
    Both endpoints must sit on the SAME line, hence the p~q coordinate checks.
    """
    def near(a: float, b: float) -> bool:
        return abs(a - b) <= eps

    if (near(abs(p.x), hw) and near(abs(p.y), hd)
            and near(abs(q.x), hw) and near(abs(q.y), hd)
            and near(p.x, q.x) and near(p.y, q.y)):
        return True
    if (near(p.z, 0.0) and near(q.z, 0.0)
            and near(abs(p.y), hd) and near(abs(q.y), hd)
            and near(p.y, q.y)):
        return True
    if (near(p.z, 0.0) and near(q.z, 0.0)
            and near(abs(p.x), hw) and near(abs(q.x), hw)
            and near(p.x, q.x)):
        return True
    return False


def _new_mesh_object(bpy, name: str, verts, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _build_body(bpy, bmesh, args):
    """Open box: 5 grid panels merged, borders welded, junctions seam-marked."""
    w, h, d = args.width_mm * MM, args.height_mm * MM, args.depth_mm * MM
    hw, hd = w / 2.0, d / 2.0
    nx = _segments(args.width_mm, args.quad_mm)
    ny = _segments(args.depth_mm, args.quad_mm)
    nz = _segments(args.height_mm, args.quad_mm)
    x_axis, y_axis, z_axis = (1, 0, 0), (0, 1, 0), (0, 0, 1)

    panels = [
        ((-hw, -hd, 0.0), x_axis, w, nx, z_axis, h, nz),   # front
        ((-hw, +hd, 0.0), x_axis, w, nx, z_axis, h, nz),   # back
        ((-hw, -hd, 0.0), y_axis, d, ny, z_axis, h, nz),   # left gusset
        ((+hw, -hd, 0.0), y_axis, d, ny, z_axis, h, nz),   # right gusset
        ((-hw, -hd, 0.0), x_axis, w, nx, y_axis, d, ny),   # bottom (no top!)
    ]
    verts: list[tuple] = []
    faces: list[tuple] = []
    for origin, ua, ul, nu, va, vl, nv in panels:
        pv, pf = _grid(origin, ua, ul, nu, va, vl, nv)
        off = len(verts)
        verts.extend(pv)
        faces.extend(tuple(i + off for i in f) for f in pf)

    obj = _new_mesh_object(bpy, "ToteBody", verts, faces)
    mesh = obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=WELD_DIST)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for e in bm.edges:
        if _is_panel_junction(e.verts[0].co, e.verts[1].co, hw, hd):
            e.seam = True
    bm.to_mesh(mesh)
    bm.free()
    return obj


def _build_strap(bpy, name: str, y_center: float, args):
    """Flat subdivided rectangle floating above the bag. Outline = boundary,
    so no seams are marked."""
    length = args.strap_length_mm * MM
    width = args.strap_width_mm * MM
    z = args.height_mm * MM + STRAP_LIFT_MM * MM
    nu = _segments(args.strap_length_mm, args.quad_mm)
    nv = _segments(args.strap_width_mm, args.quad_mm)
    verts, faces = _grid((-length / 2.0, y_center - width / 2.0, z),
                         (1, 0, 0), length, nu, (0, 1, 0), width, nv)
    return _new_mesh_object(bpy, name, verts, faces)


def _material(bpy, name: str, rgba, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba  # viewport/Workbench fallback color
    mat.use_nodes = True
    try:
        bsdf = next(n for n in mat.node_tree.nodes
                    if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    except (StopIteration, KeyError):
        pass  # node layout drift across Blender versions; fallback color set
    return mat


def _scene_bounds(bpy):
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for v in obj.data.vertices:
            co = obj.matrix_world @ v.co
            for k in range(3):
                lo[k] = min(lo[k], co[k])
                hi[k] = max(hi[k], co[k])
    return lo, hi


def _add_camera_and_sun(bpy, lo, hi):
    from mathutils import Vector
    scene = bpy.context.scene
    center = Vector(((lo[0] + hi[0]) / 2.0,
                     (lo[1] + hi[1]) / 2.0,
                     (lo[2] + hi[2]) / 2.0))
    radius = max((Vector(hi) - Vector(lo)).length / 2.0, 0.05)

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    direction = Vector((1.0, -1.0, 0.65)).normalized()  # 3/4 view: right-front-above
    distance = radius / math.sin(cam_data.angle / 2.0) * 1.15
    cam.location = center + direction * distance
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(35.0))
    scene.collection.objects.link(sun)


def _set_world(bpy):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.85, 0.86, 0.90, 1.0)
        bg.inputs[1].default_value = 1.0


def _render_png(bpy, png_path: Path) -> str:
    scene = bpy.context.scene
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    png_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(png_path)

    # Engine id changed across versions: 4.2-4.5 use BLENDER_EEVEE_NEXT,
    # older/newer use BLENDER_EEVEE. Invalid enum assignment raises TypeError.
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    try:
        bpy.ops.render.render(write_still=True)
        return scene.render.engine
    except Exception:
        traceback.print_exc()
    # EEVEE needs a GPU context, which headless/CI sessions may lack;
    # CPU Cycles always works.
    scene.render.engine = 'CYCLES'
    try:
        scene.cycles.samples = 32
        scene.cycles.device = 'CPU'
    except AttributeError:
        pass
    bpy.ops.render.render(write_still=True)
    return scene.render.engine


def _report(bpy) -> dict:
    mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH']
    seam_edges = 0
    tris = 0
    for obj in mesh_objects:
        mesh = obj.data
        seam_edges += sum(1 for e in mesh.edges if e.use_seam)
        mesh.calc_loop_triangles()
        tris += len(mesh.loop_triangles)
    return {"objects": len(mesh_objects), "seam_edges": seam_edges,
            "tris": tris}


def _draft_line() -> str:
    try:
        repo_root = str(Path(__file__).resolve().parents[1])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from pipeline.common import draft_header
        return draft_header("tote build report")
    except Exception:
        from datetime import date
        return (f"DRAFT — unverified tote build report, generated "
                f"{date.today().isoformat()} by 3D-Fabric pipeline. "
                f"AI drafts, engineers seal.")


def build_tote(args) -> dict:
    """Build the whole scene inside Blender; returns the verification report."""
    import bpy
    import bmesh

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    body = _build_body(bpy, bmesh, args)
    hd = args.depth_mm * MM / 2.0
    strap_front = _build_strap(bpy, "StrapFront", -hd, args)
    strap_back = _build_strap(bpy, "StrapBack", +hd, args)

    felt = _material(bpy, "ToteFelt", BODY_COLOR, 0.9)
    leather = _material(bpy, "StrapLeather", STRAP_COLOR, 0.6)
    body.data.materials.append(felt)
    strap_front.data.materials.append(leather)
    strap_back.data.materials.append(leather)

    lo, hi = _scene_bounds(bpy)
    _add_camera_and_sun(bpy, lo, hi)
    _set_world(bpy)

    report = _report(bpy)
    report["draft"] = _draft_line()
    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out_path), export_format='GLB')

    report["render_engine"] = _render_png(bpy, Path(args.render))
    print(f"make_tote: done {report}")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("make_tote.py builds geometry with bpy and must run inside "
              "Blender:\n  \"<blender>\" --background --python "
              "\"scripts/make_tote.py\" -- <args>", file=sys.stderr)
        return 2
    try:
        build_tote(args)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    _rc = main()
    if _rc:
        # Nonzero sys.exit propagates as Blender's process exit code, so
        # common.run_blender() can detect failure without stdout parsing.
        sys.exit(_rc)
