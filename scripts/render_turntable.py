"""Turntable video of the Crescent bag — runs INSIDE Blender:

  blender --background --python scripts/render_turntable.py -- \
      --out "designs/renders/CrescentDemo_turntable" --seconds 10

360-degree spin over the clip; the colorway switches each quarter:
espresso -> noir -> cognac -> espresso with the (placeholder) art print.
Reuses the scene builders from make_shoulder_bag.py. Outputs H.264 MP4
(Blender appends the frame range to the file stem).
"""
import argparse
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_shoulder_bag as msb  # noqa: E402

ART = Path(__file__).resolve().parent.parent / "designs/artwork/placeholder_print.png"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output path stem (no extension)")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--res-x", type=int, default=1024)
    ap.add_argument("--res-y", type=int, default=840)
    return ap.parse_args(argv)


def build_scene(a_ns):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    mat_trim = msb.leather_material("TrimLeather", (0.014, 0.012, 0.011),
                                    grain_scale=800.0, rough=0.34)
    mat_gold = msb.gold_material()
    mat_body = msb.leather_material("BodyLeather", msb.COLORWAYS["brown"])
    mat_floor = msb.flat_material("Sweep", (0.80, 0.78, 0.75), rough=0.9)
    msb.build_body(a_ns, mat_body, mat_trim)
    msb.build_shoulder_strap(a_ns, mat_trim)
    msb.build_crossbody(a_ns, mat_trim)
    msb.build_hardware(a_ns, mat_gold, mat_trim)
    msb.build_cyclorama(a_ns, mat_floor)
    msb.setup_render(a_ns)
    return mat_body


def rig_animation(mat_body, frames):
    q = frames // 4
    # Blender 5.x removed action.fcurves; steering the new-keyframe default
    # interpolation is the version-proof way to control key interpolation.
    prefs = bpy.context.preferences.edit
    # spin rig: everything except the backdrop parents to an empty
    spin = bpy.data.objects.new("Spin", None)
    bpy.context.collection.objects.link(spin)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name != "Cyclorama":
            obj.parent = spin
    prefs.keyframe_new_interpolation_type = "LINEAR"
    spin.rotation_euler = (0, 0, 0)
    spin.keyframe_insert("rotation_euler", index=2, frame=1)
    spin.rotation_euler = (0, 0, 2 * math.pi)
    spin.keyframe_insert("rotation_euler", index=2, frame=frames)

    # colorway rig: RGB color -> MixRGB (art print on top) -> Base Color
    nt = mat_body.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    rgb = nt.nodes.new("ShaderNodeRGB")
    mix = nt.nodes.new("ShaderNodeMixRGB")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(ART))
    nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], img.inputs["Vector"])
    nt.links.new(rgb.outputs[0], mix.inputs["Color1"])
    nt.links.new(img.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    prefs.keyframe_new_interpolation_type = "CONSTANT"
    segments = [(1, msb.COLORWAYS["brown"], 0.0),
                (q + 1, msb.COLORWAYS["black"], 0.0),
                (2 * q + 1, msb.COLORWAYS["cognac"], 0.0),
                (3 * q + 1, msb.COLORWAYS["brown"], 1.0)]
    for frame, rgbv, fac in segments:
        rgb.outputs[0].default_value = (*rgbv, 1.0)
        rgb.outputs[0].keyframe_insert("default_value", frame=frame)
        mix.inputs["Fac"].default_value = fac
        mix.inputs["Fac"].keyframe_insert("default_value", frame=frame)


def main():
    args = parse_args()
    frames = int(args.seconds * args.fps)
    ns = SimpleNamespace(width_mm=290.0, height_mm=170.0, depth_mm=75.0,
                         strap_width_mm=20.0, crossbody_mm=1100.0,
                         samples=args.samples)
    mat_body = build_scene(ns)
    rig_animation(mat_body, frames)

    scene = bpy.context.scene
    r = scene.render
    r.resolution_x = args.res_x
    r.resolution_y = args.res_y
    scene.frame_start = 1
    scene.frame_end = frames
    r.fps = args.fps
    # Blender 5.x has no FFMPEG render output — emit a PNG sequence; the
    # caller encodes it with ffmpeg (render pipelines do this anyway).
    r.image_settings.file_format = "PNG"
    frames_dir = Path(args.out).parent / "turntable_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    r.filepath = str(frames_dir / "frame_")
    print(f"[turntable] rendering {frames} frames @ {args.fps}fps "
          f"{args.res_x}x{args.res_y} samples={args.samples} -> {frames_dir}")
    bpy.ops.render.render(animation=True)
    print("[turntable] done")


main()
