"""Color Me Art mobile book stand — assembled display GLB for the portal.

Builds the knock-down booth from the build sheet in its deployed state:
wood frame (posts, deck, counter, shelf, roof), the three fabric wraps in
their assembled roles (scalloped roof valance, rippled side curtains,
front counter skirt with chalkboard), casters, sign panel — and three
Collection 01 bags staged on the shelf and counter, because the booth's
job is selling them.

Usage: python scripts/make_booth_glb.py [--out docs/models/color-me-art-stand.glb]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, triangulate_polygon
from trimesh.visual import TextureVisuals
from trimesh.visual.material import PBRMaterial

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_web_glb import build_bag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MM = 0.001

# lavender scheme from the build sheet (sRGB -> linear)
def lin(hexstr):
    h = hexstr.lstrip("#")
    return [(int(h[i:i + 2], 16) / 255.0) ** 2.2 for i in (0, 2, 4)]

WISTERIA = lin("B39DDB")
LILAC = lin("DCCFF0")
PLUM = lin("4A3768")
WOOD = [0.646, 0.401, 0.172]
CHALK = [0.020, 0.020, 0.024]
DARK = [0.035, 0.035, 0.038]


def flat(name, rgb, rough=0.8, metallic=0.0):
    return PBRMaterial(name=name, baseColorFactor=[*rgb, 1.0],
                       metallicFactor=metallic, roughnessFactor=rough,
                       doubleSided=True)


def bx(extents, center):
    b = box(extents=extents)
    b.apply_translation(center)
    return b


def ripple_sheet(width, drop, z_top, amp=18.0, waves=4.5, cols=48, rows=8):
    """Vertical fabric panel in the XZ plane with a soft sine ripple in Y."""
    verts, faces = [], []
    for i in range(cols + 1):
        u = i / cols
        y_off = amp * math.sin(2 * math.pi * waves * u)
        taper = 0.35 + 0.65 * (1.0 - 0.0)  # constant fullness
        for j in range(rows + 1):
            v = j / rows
            verts.append([u * width - width / 2, y_off * (0.4 + 0.6 * v) * taper,
                          z_top - v * drop])
    for i in range(cols):
        for j in range(rows):
            a = i * (rows + 1) + j
            b_ = (i + 1) * (rows + 1) + j
            faces += [[a, b_, b_ + 1], [a, b_ + 1, a + 1]]
    return trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=False)


def scallop_valance(width, drop, r):
    """Flat strip whose bottom edge is a row of hanging half-circle scallops."""
    n = max(int(width // (2 * r)), 1)
    r = width / (2 * n)
    pts = [(0.0, 0.0), (width, 0.0), (width, -(drop - r))]
    for k in range(n):
        cx = width - r - 2 * r * k
        for a in np.linspace(0.0, math.pi, 14, endpoint=(k == n - 1)):
            pts.append((cx - r * math.cos(a), -(drop - r) - r * math.sin(a)))
    pts.append((0.0, -(drop - r)))
    poly = trimesh.path.polygons.Polygon(pts)
    v2, f = triangulate_polygon(poly, engine="earcut")
    verts = np.column_stack([v2[:, 0] - width / 2, np.zeros(len(v2)), v2[:, 1]])
    return trimesh.Trimesh(vertices=verts, faces=f, process=False)


def build_booth():
    groups = {"Wood": [], "Fabric": [], "Accent": [], "Chalk": [], "Dark": []}

    # deck + casters
    groups["Wood"].append(bx((940, 560, 40), (0, 0, 170)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            wheel = cylinder(radius=45, height=24, sections=20)
            wheel.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
            wheel.apply_translation((sx * 400, sy * 220, 60))
            groups["Dark"].append(wheel)

    # posts, counter, shelf, roof
    for sx in (-1, 1):
        for sy in (-1, 1):
            groups["Wood"].append(bx((38, 38, 1700), (sx * 450, sy * 240, 1040)))
    groups["Wood"].append(bx((990, 560, 35), (0, 0, 880)))       # counter (37x20 top)
    groups["Wood"].append(bx((900, 300, 25), (0, 120, 1400)))    # display shelf
    roof = bx((1060, 640, 30), (0, 0, 1915))
    roof.apply_transform(trimesh.transformations.rotation_matrix(math.radians(4), [1, 0, 0]))
    groups["Wood"].append(roof)

    # sign board (lilac) riding proud on the valance band, like the drawing
    groups["Accent"].append(bx((720, 14, 170), (0, -334, 1800)))

    # wraps in assembled roles — wisteria 600D
    val = scallop_valance(1060, 300, 66)                          # front valance
    val.apply_translation((0, -322, 1900))
    groups["Fabric"].append(val)
    for sx in (-1, 1):                                            # side valances
        sv = scallop_valance(640, 300, 64)
        sv.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 0, 1]))
        sv.apply_translation((sx * 522, 0, 1900))
        groups["Fabric"].append(sv)
    for sx in (-1, 1):                                            # side curtains, 54 in drop
        cur = ripple_sheet(560, 1372, 1890, amp=16, waves=4.0)
        cur.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 0, 1]))
        cur.apply_translation((sx * 505, 0, 0))
        groups["Fabric"].append(cur)
    skirt = ripple_sheet(915, 460, 860, amp=12, waves=5.0)        # counter skirt, 18 in drop
    skirt.apply_translation((0, -292, 0))
    groups["Fabric"].append(skirt)

    # chalkboard on the skirt, plum frame
    groups["Accent"].append(bx((680, 12, 340), (0, -308, 620)))
    groups["Chalk"].append(bx((640, 12, 300), (0, -312, 620)))

    mats = {"Wood": flat("Wood", WOOD, 0.75), "Fabric": flat("Fabric600D", WISTERIA, 0.85),
            "Accent": flat("Accent", LILAC, 0.7), "Chalk": flat("Chalkboard", CHALK, 0.95),
            "Dark": flat("Casters", DARK, 0.6)}
    meshes = {}
    for k, parts in groups.items():
        m = trimesh.util.concatenate(parts)
        m.apply_scale(MM)
        m.visual = TextureVisuals(material=mats[k])
        meshes[k] = m
    return meshes


BAG_STAGING = [  # slug spec name, colors from collection01.json read at runtime
    ("the-313", (-260, 120, 1412), 0.0),
    ("riverwalk-blues", (150, 120, 1412), 12.0),
    ("belle-isle", (250, -60, 898), -18.0),
]


def staged_bags():
    import json
    spec = {c["slug"]: c for c in json.loads(
        (ROOT / "designs" / "collection01.json").read_text())["concepts"]}
    yup_to_zup = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
    out = {}
    for slug, (x, y, z), yaw in BAG_STAGING:
        c = spec[slug]
        scene = build_bag(c["w"], c["h"], c["d"], c["strap"], c["body"], c["trim"],
                          c.get("hw", "gold"), float(c.get("grain", 550)))
        # bag bottom in Z-up coords sits below z=0; lift so it rests on the surface
        lift = (0.68 * 0.58 - 0.12) * c["h"] * MM
        for name, geom in scene.geometry.items():
            g = geom.copy()
            g.apply_transform(yup_to_zup)
            g.apply_transform(trimesh.transformations.rotation_matrix(math.radians(yaw), [0, 0, 1]))
            g.apply_translation((x * MM, y * MM, z * MM + lift))
            out[f"{slug}-{name}"] = g
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "models" / "color-me-art-stand.glb")
    ap.add_argument("--no-bags", action="store_true")
    args = ap.parse_args()

    scene = trimesh.Scene()
    zup_to_yup = trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])
    parts = build_booth()
    if not args.no_bags:
        parts.update(staged_bags())
    for name, geom in parts.items():
        geom.apply_transform(zup_to_yup)
        scene.add_geometry(geom, node_name=name, geom_name=name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(args.out)
    tris = sum(len(g.faces) for g in scene.geometry.values())
    print(f"{args.out.name}: {args.out.stat().st_size/1024:.0f} KB, {tris} tris")


if __name__ == "__main__":
    main()
