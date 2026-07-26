"""Web-display GLBs for the portal's 3D models tab.

The pattern pipeline exports cloth-only, flat-shaded GLBs (see
make_shoulder_bag.py) — correct for flattening, ugly in a viewer. This script
rebuilds the same crescent silhouette (same profile math, same per-bag specs
from designs/collection01.json) as *display* models: smooth rounded body,
trim gusset band, leather top handle, chain links, D-rings, zipper, and PBR
materials. Pure Python (trimesh) — no Blender needed, so it runs anywhere.

Usage:
  python scripts/make_web_glb.py                        # all collection bags + CrescentDemo
  python scripts/make_web_glb.py --only belle-isle      # one bag
  python scripts/make_web_glb.py --out-dir docs/models  # (default)
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, torus, triangulate_polygon
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

ROOT = Path(__file__).resolve().parent.parent
M = 0.001  # mm -> m

GOLD = dict(baseColorFactor=[0.85, 0.62, 0.25, 1.0], metallicFactor=1.0, roughnessFactor=0.25)
SILVER = dict(baseColorFactor=[0.75, 0.77, 0.80, 1.0], metallicFactor=1.0, roughnessFactor=0.20)


# ---------------------------------------------------------- silhouette math
# identical to scripts/make_shoulder_bag.py so web models match the patterns

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
    return np.array(pts, dtype=float)


def top_arc(w, h, t):
    hw = w / 2.0
    top_z, peak_z = 0.42 * h, 0.52 * h
    x = -hw * 0.94 + t * (2 * hw * 0.94)
    return x, top_z + (peak_z - top_z) * math.sin(math.pi * t)


def strap_arc(w, h, t, apex=0.095):
    hw = w / 2.0 * M
    top = 0.42 * h * M
    span = hw * 0.62
    return np.array([-span + 2 * span * t, 0.0, top + apex * math.sin(math.pi * t)])


# ---------------------------------------------------------------- helpers

def pbr(name, rgb, rough=0.45, metallic=0.0):
    return PBRMaterial(name=name, baseColorFactor=[*rgb, 1.0],
                       metallicFactor=metallic, roughnessFactor=rough,
                       doubleSided=True)


def with_material(mesh, mat):
    mesh.visual = TextureVisuals(material=mat)
    return mesh


def polygon_normals(pts):
    """Per-vertex outward normals of a closed 2D polygon (angle-bisector)."""
    n = len(pts)
    nrm = np.zeros_like(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        e0 = p1 - p0
        e1 = p2 - p1
        n0 = np.array([e0[1], -e0[0]])
        n1 = np.array([e1[1], -e1[0]])
        v = n0 / (np.linalg.norm(n0) + 1e-12) + n1 / (np.linalg.norm(n1) + 1e-12)
        ln = np.linalg.norm(v)
        nrm[i] = v / ln if ln > 1e-9 else n0 / (np.linalg.norm(n0) + 1e-12)
    # make outward: point away from centroid on average
    c = pts.mean(axis=0)
    if np.mean(np.einsum("ij,ij->i", nrm, pts - c)) < 0:
        nrm = -nrm
    return nrm


def ensure_ccw(pts):
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    return pts[::-1].copy() if area < 0 else pts


def loft_band(sections):
    """Closed ring strip through a list of same-length 3D loops."""
    sections = [np.asarray(s) for s in sections]
    n = len(sections[0])
    verts = np.vstack(sections)
    faces = []
    for k in range(len(sections) - 1):
        a, b = k * n, (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces.append([a + i, a + j, b + j])
            faces.append([a + i, b + j, b + i])
    m = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)
    # orient outward
    c = verts.mean(axis=0)
    fc = m.triangles_center - c
    if np.mean(np.einsum("ij,ij->i", m.face_normals, fc)) < 0:
        m.invert()
    return m


def cap_mesh(loop2d, y, flip):
    poly = trimesh.path.polygons.Polygon(loop2d)
    v2, f = triangulate_polygon(poly, engine="earcut")
    verts = np.column_stack([v2[:, 0], np.full(len(v2), y), v2[:, 1]])
    m = trimesh.Trimesh(vertices=verts, faces=f, process=False)
    want = np.array([0.0, -1.0, 0.0]) if flip else np.array([0.0, 1.0, 0.0])
    if np.mean(m.face_normals @ want) < 0:
        m.invert()
    return m


def sweep_strip(path_pts, width_y, thick, sections=8):
    """Sweep a rounded-rect cross-section along a 3D path lying in XZ."""
    # cross-section outline in (u=thickness dir, v=y) local coords
    hw, ht = width_y / 2.0, thick / 2.0
    cs = []
    for i in range(sections):
        a = 2 * math.pi * i / sections
        cs.append((ht * math.copysign(min(1.0, abs(math.cos(a)) * 1.4), math.cos(a)),
                   hw * math.copysign(min(1.0, abs(math.sin(a)) * 1.4), math.sin(a))))
    cs = np.array(cs)
    loops = []
    for k, p in enumerate(path_pts):
        p_prev = path_pts[max(k - 1, 0)]
        p_next = path_pts[min(k + 1, len(path_pts) - 1)]
        t = p_next - p_prev
        t = t / (np.linalg.norm(t) + 1e-12)
        nrm = np.array([-t[2], 0.0, t[0]])  # in-plane normal
        loop = [p + u * nrm + np.array([0.0, v, 0.0]) for u, v in cs]
        loops.append(np.array(loop))
    band = loft_band(loops)
    caps = []
    for idx, flipd in ((0, True), (-1, False)):
        loop = loops[idx]
        center = loop.mean(axis=0)
        n = len(loop)
        fv = np.vstack([loop, center])
        f = [[i, (i + 1) % n, n] for i in range(n)]
        cm = trimesh.Trimesh(vertices=fv, faces=f, process=False)
        caps.append(cm)
    return trimesh.util.concatenate([band] + caps)


def chain_link(p, tangent, roll_vertical, scale_along=1.35):
    t = tangent / (np.linalg.norm(tangent) + 1e-12)
    link = torus(major_radius=0.0085, minor_radius=0.0017,
                 major_sections=20, minor_sections=8)
    S = np.eye(4)
    S[0, 0] = scale_along
    S[2, 2] = 0.8
    link.apply_transform(S)
    if roll_vertical:  # plane contains tangent + Z
        link.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    pitch = math.atan2(t[2], t[0])
    link.apply_transform(trimesh.transformations.rotation_matrix(pitch, [0, -1, 0]))
    link.apply_translation(p)
    return link


# ---------------------------------------------------------------- assembly

def build_bag(w, h, d, strap_w, body_rgb, trim_rgb, hw_kind):
    dhalf = d * M / 2.0
    prof = ensure_ccw(profile_points(w, h)) * M
    nrm = polygon_normals(prof)

    # rounded gusset: inward offset follows a quarter-circle near each face
    r = min(0.014, dhalf * 0.55)
    stations, loops = [], []
    K = 9
    for k in range(K + 1):
        y = -dhalf + (2 * dhalf) * k / K
        edge = abs(y) - (dhalf - r)
        off = 0.0 if edge <= 0 else r - math.sqrt(max(r * r - edge * edge, 0.0))
        loops.append(np.column_stack([prof[:, 0] - nrm[:, 0] * off,
                                      np.full(len(prof), y),
                                      prof[:, 1] - nrm[:, 1] * off]))
        stations.append(off)
    band = loft_band(loops)

    cap_off = stations[0]
    cap_loop = prof - nrm * cap_off
    front = cap_mesh(cap_loop, -dhalf, flip=True)
    back = cap_mesh(cap_loop, dhalf, flip=False)

    # leather handle (chain covers t<0.17 and t>0.83)
    handle_pts = np.array([strap_arc(w, h, 0.17 + (0.83 - 0.17) * i / 24.0) for i in range(25)])
    handle = sweep_strip(handle_pts, strap_w * M, 0.004)

    hw_mat = pbr("Hardware", GOLD["baseColorFactor"][:3] if hw_kind == "gold" else SILVER["baseColorFactor"][:3],
                 rough=(GOLD if hw_kind == "gold" else SILVER)["roughnessFactor"],
                 metallic=1.0)

    hardware = []
    for t_end in (0.0, 1.0):
        p = strap_arc(w, h, t_end)
        ring = torus(major_radius=0.011, minor_radius=0.0022,
                     major_sections=20, minor_sections=8)
        ring.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        ring.apply_translation(p - np.array([0, 0, 0.004]))
        hardware.append(ring)
    for t0, t1 in ((0.015, 0.165), (0.835, 0.985)):
        n = 7
        for i in range(n):
            t = t0 + (t1 - t0) * i / (n - 1)
            p = strap_arc(w, h, t)
            p2 = strap_arc(w, h, t + 0.01)
            hardware.append(chain_link(p, p2 - p, roll_vertical=(i % 2 == 0)))
    # zipper bead along the top arc + slider + pull
    zip_pts = [np.array([x * M, 0.0, z * M + 0.0012]) for x, z in
               (top_arc(w, h, i / 30.0) for i in range(31))]
    for a, b in zip(zip_pts[:-1], zip_pts[1:]):
        hardware.append(cylinder(radius=0.0016, segment=(a, b), sections=8))
    sx, sz = top_arc(w, h, 0.30)
    slider = box(extents=(0.012, 0.007, 0.0056))
    slider.apply_translation((sx * M, 0, sz * M + 0.0022))
    hardware.append(slider)
    pull = torus(major_radius=0.006, minor_radius=0.0012, major_sections=16, minor_sections=6)
    pull.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 5, [0, 1, 0]))
    pull.apply_translation((sx * M + 0.004, 0, sz * M - 0.004))
    hardware.append(pull)

    panels = with_material(trimesh.util.concatenate([front, back]),
                           pbr("BodyLeather", body_rgb, rough=0.5))
    trim = with_material(trimesh.util.concatenate([band, handle]),
                         pbr("TrimLeather", trim_rgb, rough=0.45))
    hw_mesh = with_material(trimesh.util.concatenate(hardware), hw_mat)

    scene = trimesh.Scene()
    zup_to_yup = trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])
    for name, geom in (("Panels", panels), ("Trim", trim), ("Hardware", hw_mesh)):
        geom.apply_transform(zup_to_yup)
        scene.add_geometry(geom, node_name=name, geom_name=name)
    return scene


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "models")
    ap.add_argument("--collection", type=Path, default=ROOT / "designs" / "collection01.json")
    ap.add_argument("--only", default=None, help="single slug to rebuild")
    args = ap.parse_args()

    spec = json.loads(args.collection.read_text(encoding="utf-8"))
    concepts = list(spec["concepts"])
    concepts.append({  # the original demo, brown colorway
        "slug": "CrescentDemo", "w": 290, "h": 170, "d": 75, "strap": 20,
        "body": [0.085, 0.042, 0.024], "trim": [0.014, 0.012, 0.011], "hw": "gold",
    })
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for c in concepts:
        if args.only and c["slug"] != args.only:
            continue
        scene = build_bag(c["w"], c["h"], c["d"], c["strap"],
                          c["body"], c["trim"], c.get("hw", "gold"))
        out = args.out_dir / f"{c['slug']}.glb"
        scene.export(out)
        tris = sum(len(g.faces) for g in scene.geometry.values())
        print(f"{out.name:34s} {out.stat().st_size/1024:7.0f} KB  {tris:6d} tris")


if __name__ == "__main__":
    main()
