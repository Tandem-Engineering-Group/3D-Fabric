"""Web-display GLBs for the portal's 3D models tab.

The pattern pipeline exports cloth-only, flat-shaded GLBs (see
make_shoulder_bag.py) — correct for flattening, ugly in a viewer. This script
rebuilds the same crescent silhouette (same profile math, same per-bag specs
from designs/collection01.json) as *display* models: puffed body panels,
trim gusset band, leather top handle, chain links, D-rings, zipper, geometric
topstitching, and a baked pebble-leather texture set (normal + albedo +
roughness). Pure Python (trimesh + scipy) — no Blender needed.

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
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from trimesh.creation import box, cylinder, torus, triangulate_polygon
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

ROOT = Path(__file__).resolve().parent.parent
M = 0.001  # mm -> m

GOLD = ([0.85, 0.62, 0.25], 0.25)
SILVER = ([0.75, 0.77, 0.80], 0.20)
TEX_CELLS = 16          # pebble cells across one texture tile
TEX_SIZE = 512


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


# ------------------------------------------------------------ leather tiles

def pebble_textures(seed=313):
    """Tileable pebble-leather set: (albedo, normal, metallicRoughness)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((TEX_CELLS * TEX_CELLS // 8 + TEX_CELLS, 2))
    # wrap 3x3 for a seamless tile
    offs = np.array([(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    wrapped = (pts[None, :, :] + offs[:, None, :]).reshape(-1, 2)
    ids = np.tile(np.arange(len(pts)), 9)
    tree = cKDTree(wrapped)
    g = (np.arange(TEX_SIZE) + 0.5) / TEX_SIZE
    gx, gy = np.meshgrid(g, g)
    q = np.column_stack([gx.ravel(), gy.ravel()])
    d, idx = tree.query(q, k=1)
    d = d.reshape(TEX_SIZE, TEX_SIZE)
    cell = ids[idx].reshape(TEX_SIZE, TEX_SIZE)
    d95 = np.quantile(d, 0.95)
    height = np.clip(1.0 - (d / d95) ** 1.5, 0.0, 1.0)          # domed pebbles
    height = gaussian_filter(height, 1.2, mode="wrap")
    fine = gaussian_filter(rng.random((TEX_SIZE, TEX_SIZE)), 1.0, mode="wrap")
    height = height + 0.10 * (fine - 0.5)

    # tangent-space normal map from the height gradient
    strength = 5.0
    dy_, dx_ = np.gradient(height)
    nz = np.ones_like(height) / strength
    ln = np.sqrt(dx_ ** 2 + dy_ ** 2 + nz ** 2)
    nrm = np.stack([-dx_ / ln, dy_ / ln, nz / ln], axis=-1)
    normal_img = Image.fromarray(((nrm * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")

    # albedo: near-white multiplier with per-pebble tint + crevice darkening
    cell_tint = rng.uniform(-1.0, 1.0, len(pts))[cell]
    alb = 238 + 8 * cell_tint + 14 * (height - 0.6)
    alb = np.clip(alb, 0, 255).astype(np.uint8)
    albedo_img = Image.fromarray(np.stack([alb] * 3, axis=-1), "RGB")

    # glTF metallicRoughness: G = roughness, B = metallic
    rough = np.clip(0.62 - 0.22 * height + 0.10 * (fine - 0.5), 0.0, 1.0)
    mr = np.zeros((TEX_SIZE, TEX_SIZE, 3), dtype=np.uint8)
    mr[:, :, 1] = (rough * 255).astype(np.uint8)
    mr_img = Image.fromarray(mr, "RGB")
    return albedo_img, normal_img, mr_img


_TILES = None


def leather_pbr(name, rgb, grain):
    global _TILES
    if _TILES is None:
        _TILES = pebble_textures()
    albedo, normal, mr = _TILES
    return PBRMaterial(name=name,
                       baseColorFactor=[*rgb, 1.0],
                       baseColorTexture=albedo,
                       normalTexture=normal,
                       metallicRoughnessTexture=mr,
                       metallicFactor=0.0, roughnessFactor=1.0,
                       doubleSided=True), grain / TEX_CELLS  # UV repeats per meter


def metal_pbr(kind):
    rgb, rough = GOLD if kind == "gold" else SILVER
    return PBRMaterial(name="Hardware", baseColorFactor=[*rgb, 1.0],
                       metallicFactor=1.0, roughnessFactor=rough,
                       doubleSided=True)


def flat_pbr(name, rgb, rough):
    return PBRMaterial(name=name, baseColorFactor=[*rgb, 1.0],
                       metallicFactor=0.0, roughnessFactor=rough,
                       doubleSided=True)


# ---------------------------------------------------------------- geometry

def polygon_normals(pts):
    """Per-vertex outward normals of a closed 2D polygon (angle-bisector)."""
    n = len(pts)
    nrm = np.zeros_like(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        e0, e1 = p1 - p0, p2 - p1
        n0 = np.array([e0[1], -e0[0]])
        n1 = np.array([e1[1], -e1[0]])
        v = n0 / (np.linalg.norm(n0) + 1e-12) + n1 / (np.linalg.norm(n1) + 1e-12)
        ln = np.linalg.norm(v)
        nrm[i] = v / ln if ln > 1e-9 else n0 / (np.linalg.norm(n0) + 1e-12)
    c = pts.mean(axis=0)
    if np.mean(np.einsum("ij,ij->i", nrm, pts - c)) < 0:
        nrm = -nrm
    return nrm


def ensure_ccw(pts):
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    return pts[::-1].copy() if area < 0 else pts


def loft_band(sections):
    """Closed ring strip through same-length 3D loops. Returns (mesh, rows, n)."""
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
    c = verts.mean(axis=0)
    if np.mean(np.einsum("ij,ij->i", m.face_normals, m.triangles_center - c)) < 0:
        m.invert()
    return m


def dome_cap(loop2d, nrm2d, y, dome, flip):
    """Puffed panel: rings inset toward the centroid, bulging outward."""
    c = loop2d.mean(axis=0)
    fr = [0.0, 0.16, 0.36, 0.60, 0.82]
    rings = []
    for f in fr:
        ring2 = c + (loop2d - c) * (1.0 - f)
        bulge = dome * math.sqrt(max(0.0, 1.0 - (1.0 - f) ** 2))
        yy = y - bulge if flip else y + bulge
        rings.append(np.column_stack([ring2[:, 0], np.full(len(ring2), yy), ring2[:, 1]]))
    n = len(loop2d)
    verts = np.vstack(rings)
    faces = []
    for k in range(len(rings) - 1):
        a, b = k * n, (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces.append([a + i, a + j, b + j])
            faces.append([a + i, b + j, b + i])
    center = np.array([c[0], y - dome if flip else y + dome, c[1]])
    ci = len(verts)
    verts = np.vstack([verts, center])
    a = (len(rings) - 1) * n
    for i in range(n):
        faces.append([a + i, a + (i + 1) % n, ci])
    m = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)
    want = np.array([0.0, -1.0, 0.0]) if flip else np.array([0.0, 1.0, 0.0])
    if np.mean(m.face_normals @ want) < 0:
        m.invert()
    uv = np.column_stack([verts[:, 0], verts[:, 2]])
    return m, uv


def sweep_strip(path_pts, width_y, thick, sections=8):
    """Sweep a soft cross-section along a 3D path lying in XZ. Returns (mesh, uv)."""
    hw, ht = width_y / 2.0, thick / 2.0
    cs = []
    for i in range(sections):
        a = 2 * math.pi * i / sections
        cs.append((ht * math.copysign(min(1.0, abs(math.cos(a)) * 1.4), math.cos(a)),
                   hw * math.copysign(min(1.0, abs(math.sin(a)) * 1.4), math.sin(a))))
    cs = np.array(cs)
    loops, arc = [], [0.0]
    for k, p in enumerate(path_pts):
        p_prev = path_pts[max(k - 1, 0)]
        p_next = path_pts[min(k + 1, len(path_pts) - 1)]
        t = p_next - p_prev
        t = t / (np.linalg.norm(t) + 1e-12)
        nrm = np.array([-t[2], 0.0, t[0]])
        loops.append(np.array([p + u * nrm + np.array([0.0, v, 0.0]) for u, v in cs]))
        if k:
            arc.append(arc[-1] + float(np.linalg.norm(path_pts[k] - path_pts[k - 1])))
    band = loft_band(loops)
    uv_band = np.array([[arc[k], i * (2 * (hw + ht)) / sections]
                        for k in range(len(loops)) for i in range(sections)])
    parts, uvs = [band], [uv_band]
    for idx, _ in ((0, True), (-1, False)):
        loop = loops[idx]
        center = loop.mean(axis=0)
        fv = np.vstack([loop, center])
        f = [[i, (i + 1) % sections, sections] for i in range(sections)]
        parts.append(trimesh.Trimesh(vertices=fv, faces=f, process=False))
        uvs.append(np.column_stack([fv[:, 0], fv[:, 2]]))
    mesh = trimesh.util.concatenate(parts)
    return mesh, np.vstack(uvs)


def chain_link(p, tangent, roll_vertical, scale_along=1.35):
    t = tangent / (np.linalg.norm(tangent) + 1e-12)
    link = torus(major_radius=0.0085, minor_radius=0.0017,
                 major_sections=20, minor_sections=8)
    S = np.eye(4)
    S[0, 0] = scale_along
    S[2, 2] = 0.8
    link.apply_transform(S)
    if roll_vertical:
        link.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    pitch = math.atan2(t[2], t[0])
    link.apply_transform(trimesh.transformations.rotation_matrix(pitch, [0, -1, 0]))
    link.apply_translation(p)
    return link


def stitch_dashes(path_pts, radius=0.00045, dash=0.0022, pitch=0.0045, closed=False):
    """Topstitch: short thread dashes along a 3D polyline."""
    pts = np.asarray(path_pts)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    seg = np.diff(pts, axis=0)
    seglen = np.linalg.norm(seg, axis=1)
    total = seglen.sum()
    cum = np.concatenate([[0.0], np.cumsum(seglen)])
    dashes = []
    s = pitch / 2.0
    while s < total - dash:
        k = int(np.searchsorted(cum, s, side="right")) - 1
        k = min(k, len(seg) - 1)
        t = seg[k] / (seglen[k] + 1e-12)
        p = pts[k] + t * (s - cum[k])
        dashes.append(cylinder(radius=radius, segment=(p, p + t * dash), sections=6))
        s += pitch
    return dashes


# ---------------------------------------------------------------- assembly

def build_bag(w, h, d, strap_w, body_rgb, trim_rgb, hw_kind, grain):
    dhalf = d * M / 2.0
    prof = ensure_ccw(profile_points(w, h)) * M
    nrm = polygon_normals(prof)

    body_mat, rep_body = leather_pbr("BodyLeather", body_rgb, grain)
    trim_mat, rep_trim = leather_pbr("TrimLeather", trim_rgb, grain * 1.25)
    thread_rgb = [min(1.0, c * 1.5 + 0.18) for c in trim_rgb]
    thread_mat = flat_pbr("Thread", thread_rgb, rough=0.65)

    # --- gusset band with rounded rim
    r = min(0.014, dhalf * 0.55)
    loops, arc = [], [0.0]
    K = 9
    for k in range(K + 1):
        y = -dhalf + (2 * dhalf) * k / K
        edge = abs(y) - (dhalf - r)
        off = 0.0 if edge <= 0 else r - math.sqrt(max(r * r - edge * edge, 0.0))
        loops.append(np.column_stack([prof[:, 0] - nrm[:, 0] * off,
                                      np.full(len(prof), y),
                                      prof[:, 1] - nrm[:, 1] * off]))
    band = loft_band(loops)
    ds = np.linalg.norm(np.diff(np.vstack([prof, prof[:1]]), axis=0), axis=1)
    u_prof = np.concatenate([[0.0], np.cumsum(ds[:-1])])
    uv_band = np.array([[u_prof[i], loops[k][0, 1]]
                        for k in range(K + 1) for i in range(len(prof))])

    # --- puffed panels (outline matches the band's rounded rim at y = ±dhalf)
    dome = min(0.009, dhalf * 0.40)
    cap_off = r  # band offset at the extreme stations
    cap_loop = prof - nrm * cap_off
    front, uv_f = dome_cap(cap_loop, nrm, -dhalf, dome, flip=True)
    back, uv_b = dome_cap(cap_loop, nrm, dhalf, dome, flip=False)

    # --- leather handle (chain covers t<0.17 and t>0.83)
    handle_pts = np.array([strap_arc(w, h, 0.17 + (0.83 - 0.17) * i / 24.0) for i in range(25)])
    handle, uv_h = sweep_strip(handle_pts, strap_w * M, 0.004)

    # --- topstitching
    stitches = []
    inset = 0.005
    for y_side, flip in ((-dhalf, True), (dhalf, False)):
        ring2 = prof - nrm * (cap_off + inset)
        c2 = cap_loop.mean(axis=0)
        f = inset / (np.linalg.norm(cap_loop - c2, axis=1) + 1e-9)
        bulge = dome * np.sqrt(np.clip(1.0 - (1.0 - f) ** 2, 0.0, 1.0)) + 0.0006
        yy = y_side - bulge if flip else y_side + bulge
        ring3 = np.column_stack([ring2[:, 0], yy, ring2[:, 1]])
        stitches += stitch_dashes(ring3, closed=True)
    for side in (-1.0, 1.0):
        line = handle_pts.copy()
        tang = np.gradient(handle_pts, axis=0)
        tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-12
        nvec = np.column_stack([-tang[:, 2], np.zeros(len(tang)), tang[:, 0]])
        line = line + nvec * 0.0024 + np.array([0.0, side * (strap_w * M / 2 - 0.003), 0.0])
        stitches += stitch_dashes(line)

    # --- hardware
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

    # --- group by material, attach UVs (repeats-per-meter scaling)
    panels = trimesh.util.concatenate([front, back])
    panels.visual = TextureVisuals(uv=np.vstack([uv_f, uv_b]) * rep_body, material=body_mat)
    trim = trimesh.util.concatenate([band, handle])
    trim.visual = TextureVisuals(uv=np.vstack([uv_band, uv_h]) * rep_trim, material=trim_mat)
    hw_mesh = trimesh.util.concatenate(hardware)
    hw_mesh.visual = TextureVisuals(material=metal_pbr(hw_kind))
    st_mesh = trimesh.util.concatenate(stitches)
    st_mesh.visual = TextureVisuals(material=thread_mat)

    scene = trimesh.Scene()
    zup_to_yup = trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])
    for name, geom in (("Panels", panels), ("Trim", trim),
                       ("Hardware", hw_mesh), ("Stitches", st_mesh)):
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
        "body": [0.085, 0.042, 0.024], "trim": [0.014, 0.012, 0.011],
        "hw": "gold", "grain": 550,
    })
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for c in concepts:
        if args.only and c["slug"] != args.only:
            continue
        scene = build_bag(c["w"], c["h"], c["d"], c["strap"],
                          c["body"], c["trim"], c.get("hw", "gold"),
                          float(c.get("grain", 550)))
        out = args.out_dir / f"{c['slug']}.glb"
        scene.export(out)
        tris = sum(len(g.faces) for g in scene.geometry.values())
        print(f"{out.name:34s} {out.stat().st_size/1024:7.0f} KB  {tris:6d} tris")


if __name__ == "__main__":
    main()
