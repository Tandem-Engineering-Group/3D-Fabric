"""The 'input' graphic: the reference bag reduced to the geometry we actually
took from it — profile curve, strap arc, chain zones. Clean line drawing."""
import math

from PIL import Image, ImageDraw

W, H = 1400, 1150
img = Image.new("RGB", (W, H), "#F5F1EA")
d = ImageDraw.Draw(img)

INK = "#2B1B12"
GOLD = "#9A5B33"

# same profile math as make_shoulder_bag.py, drawn flat
w_mm, h_mm = 290.0, 170.0
S = 3.1          # mm -> px
CX, CY = W / 2, H * 0.62


def P(x, z):
    return (CX + x * S, CY - z * S)


hw = w_mm / 2
top_z, peak_z = 0.42 * h_mm, 0.52 * h_mm
side_z = 0.12 * h_mm
rz = 0.68 * h_mm
pts = [P(hw * 0.965, top_z), P(hw, side_z)]
for i in range(1, 25):
    th = math.pi * i / 25.0
    pts.append(P(hw * math.cos(th), side_z - rz * math.sin(th) * 0.58))
pts.append(P(-hw, side_z))
pts.append(P(-hw * 0.965, top_z))
for i in range(1, 12):
    t = i / 12.0
    x = -hw * 0.965 + t * (2 * hw * 0.965)
    pts.append(P(x, top_z + (peak_z - top_z) * math.sin(math.pi * t)))
d.line(pts + [pts[0]], fill=INK, width=9, joint="curve")

# strap arc with chain-zone ends
span = hw * 0.62
apex = 95.0
strap = []
for i in range(49):
    t = i / 48.0
    strap.append(P(-span + 2 * span * t, top_z + apex * math.sin(math.pi * t)))
d.line(strap[8:41], fill=INK, width=9, joint="curve")
for seg in (strap[0:9], strap[40:49]):          # chain zones as dotted gold
    for k, p in enumerate(seg):
        if k % 2 == 0:
            d.ellipse([p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7], outline=GOLD, width=5)

# zipper line + annotation ticks
zip_pts = []
for i in range(31):
    t = i / 30.0
    x = -hw * 0.94 + t * (2 * hw * 0.94)
    zip_pts.append(P(x, top_z + (peak_z - top_z) * math.sin(math.pi * t) - 6))
d.line(zip_pts, fill=GOLD, width=4)

d.text((CX - 260, H * 0.88), "the reference, reduced to what we took: geometry",
       fill="#8A7B6C")
d.text((CX - 170, H * 0.915), "(logos, monogram, brand hardware: left behind)",
       fill="#8A7B6C")
img.save(r"C:\23 Erika Purse Buisness\designs\renders\collection\input_silhouette.png")
print("wrote input_silhouette.png")
