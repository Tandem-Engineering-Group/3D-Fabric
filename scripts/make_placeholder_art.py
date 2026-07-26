"""Original placeholder print pattern (stands in for Color Me Art files).
Deterministic seeded doodle: bold organic blobs + line work, portrait panel."""
import math
import random

from PIL import Image, ImageDraw

rng = random.Random(20260726)
W, H = 1200, 1200
PALETTE = ["#E2543E", "#F2B33D", "#3E7CB1", "#2C6E49", "#7D4E9F", "#F5EBDD"]

img = Image.new("RGB", (W, H), "#F5EBDD")
d = ImageDraw.Draw(img)

for _ in range(26):
    cx, cy = rng.uniform(0, W), rng.uniform(0, H)
    r = rng.uniform(60, 190)
    color = rng.choice(PALETTE[:-1])
    pts = []
    for k in range(24):
        th = 2 * math.pi * k / 24
        rr = r * rng.uniform(0.75, 1.25)
        pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
    d.polygon(pts, fill=color)

for _ in range(40):
    x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
    ang = rng.uniform(0, 2 * math.pi)
    ln = rng.uniform(80, 260)
    x1, y1 = x0 + ln * math.cos(ang), y0 + ln * math.sin(ang)
    d.line([(x0, y0), (x1, y1)], fill=rng.choice(PALETTE), width=rng.randint(6, 14))

for _ in range(120):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    r = rng.uniform(4, 14)
    d.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(PALETTE))

d.text((18, H - 34), "PLACEHOLDER ART - not Color Me Art", fill="#00000088")
out = r"C:\23 Erika Purse Buisness\designs\artwork\placeholder_print.png"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print("wrote", out)
