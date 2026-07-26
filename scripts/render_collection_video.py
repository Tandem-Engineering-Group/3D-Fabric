"""Collection reel — runs INSIDE Blender. One segment per concept with varied
camera moves (orbit / dolly-in / crane-down cycling), tracked on the bag:

  blender --background --python-exit-code 1 --python scripts/render_collection_video.py -- \
      --manifest designs/collection01.json --frames-dir designs/renders/reel_frames \
      [--frames-per 36] [--samples 40]

Outputs numbered PNG segment folders (00_the-313/frame_0001.png ...); the
caller encodes + concatenates with ffmpeg.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_shoulder_bag as msb  # noqa: E402
from render_collection import hardware_material  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--frames-per", type=int, default=36)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--res-x", type=int, default=1024)
    ap.add_argument("--res-y", type=int, default=840)
    ap.add_argument("--move", choices=["cycle", "orbit"], default="cycle",
                    help="cycle: orbit/dolly/crane per segment; orbit: one "
                         "seamless 360-degree circle across all segments")
    return ap.parse_args(argv)


def build_concept_scene(c, samples):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.curves, bpy.data.actions):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    ns = SimpleNamespace(width_mm=float(c["w"]), height_mm=float(c["h"]),
                         depth_mm=float(c["d"]), strap_width_mm=float(c["strap"]),
                         crossbody_mm=1100.0, samples=samples)
    mat_body = msb.leather_material(f"Body_{c['slug']}", tuple(c["body"]),
                                    grain_scale=float(c["grain"]), rough=0.40)
    mat_trim = msb.leather_material(f"Trim_{c['slug']}", tuple(c["trim"]),
                                    grain_scale=800.0, rough=0.36)
    msb.build_body(ns, mat_body, mat_trim)
    msb.build_shoulder_strap(ns, mat_trim)
    msb.build_crossbody(ns, mat_trim)
    msb.build_hardware(ns, hardware_material(c["hw"]), mat_trim)
    msb.build_cyclorama(ns, msb.flat_material("Sweep", (0.80, 0.78, 0.75), 0.9))
    msb.setup_render(ns)
    return ns


def rig_camera_move(c, move, frames, seg_index=0, seg_count=1):
    """Replace the static camera pose with an animated one, always tracking
    the bag. Moves 0-2: orbit sweep / dolly-in / crane-down. Move "orbit-slice"
    (via seg_count>1 and move==3): this segment covers its share of one
    continuous 360-degree circle at FIXED radius and height, so concatenated
    segments play as a single seamless orbit while the bag changes."""
    scene = bpy.context.scene
    cam = scene.camera
    f = float(c.get("cam", 1.0)) if move != 3 else 1.05
    base = tuple(v * f for v in (0.46, -0.60, 0.18))

    target = bpy.data.objects.new("CamTarget", None)
    target.location = (0.0, 0.0, 0.015)
    bpy.context.collection.objects.link(target)
    tr = cam.constraints.new("TRACK_TO")
    tr.target = target
    tr.track_axis = "TRACK_NEGATIVE_Z"
    tr.up_axis = "UP_Y"

    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = "LINEAR"

    def key(loc, frame):
        cam.location = loc
        cam.keyframe_insert("location", frame=frame)

    if move == 0:  # orbit: swing around the bag by ~50 degrees
        r = math.hypot(base[0], base[1])
        a0 = math.atan2(base[1], base[0]) - math.radians(25)
        a1 = a0 + math.radians(50)
        key((r * math.cos(a0), r * math.sin(a0), base[2]), 1)
        key((r * math.cos(a1), r * math.sin(a1), base[2]), frames)
    elif move == 1:  # dolly-in: low and far -> close and level
        key((base[0] * 1.35, base[1] * 1.35, base[2] * 0.45), 1)
        key((base[0] * 0.92, base[1] * 0.92, base[2] * 1.05), frames)
    else:  # crane-down: high overhead -> settle at the hero angle
        key((base[0] * 0.75, base[1] * 0.75, base[2] + 0.34), 1)
        key((base[0], base[1], base[2] * 0.95), frames)


def rig_bag_spin(seg_index, seg_count, frames):
    """Turntable, done right for a one-sided studio sweep: the BAG rotates,
    camera and backdrop stay put — a camera orbit would stare at the back of
    the cyclorama for half the circle. Segment i covers its slice of one full
    revolution; the end key sits one frame past the segment so concatenated
    cuts land exactly on the next segment's first frame."""
    spin = bpy.data.objects.new("Spin", None)
    bpy.context.collection.objects.link(spin)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name != "Cyclorama":
            obj.parent = spin
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    seg = 2 * math.pi / seg_count
    spin.rotation_euler = (0, 0, seg_index * seg)
    spin.keyframe_insert("rotation_euler", index=2, frame=1)
    spin.rotation_euler = (0, 0, (seg_index + 1) * seg)
    spin.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
    cam = bpy.context.scene.camera
    cam.location = tuple(v * 1.05 for v in (0.46, -0.60, 0.18))


def main():
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    scene = None
    n = len(manifest["concepts"])
    for i, c in enumerate(manifest["concepts"]):
        build_concept_scene(c, args.samples)
        if args.move == "orbit":
            rig_bag_spin(i, n, args.frames_per)
        else:
            rig_camera_move(c, i % 3, args.frames_per)
        scene = bpy.context.scene
        scene.render.resolution_x = args.res_x
        scene.render.resolution_y = args.res_y
        scene.frame_start = 1
        scene.frame_end = args.frames_per
        scene.render.fps = args.fps
        scene.render.image_settings.file_format = "PNG"
        seg = Path(args.frames_dir) / f"{i:02d}_{c['slug']}"
        seg.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(seg / "frame_")
        print(f"[reel] {c['slug']} move={i % 3} rendering "
              f"{args.frames_per} frames", flush=True)
        bpy.ops.render.render(animation=True)
    print("[reel] all segments rendered")


main()
