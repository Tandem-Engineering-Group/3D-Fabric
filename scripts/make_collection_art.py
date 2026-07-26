"""Three more original placeholder prints (stand-ins for Color Me Art files).
Each has its own palette + motif; all stamped as placeholders."""
import math
import os
import random

from PIL import Image, ImageDraw

OUT_DIR = r"C:\23 Erika Purse Buisness\designs\artwork"
os.makedirs(OUT_DIR, exist_ok=True)
W = H = 1200
STAMP = "PLACEHOLDER ART - not Color Me Art"


def canvas(bg):
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def blob(d, rng, cx, cy, r, color, wobble=0.3):
    pts = []
    for k in range(26):
        th = 2 * math.pi * k / 26
        rr = r * rng.uniform(1 - wobble, 1 + wobble)
        pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
    d.polygon(pts, fill=color)


# --- Eastern Market: produce + flowers on cream -----------------------------
rng = random.Random(313001)
img, d = canvas("#F2E9D8")
PAL = ["#D7402B", "#E89B1C", "#3E7C3A", "#7A9E43", "#B23A48"]
for _ in range(18):
    cx, cy = rng.uniform(0, W), rng.uniform(0, H)
    blob(d, rng, cx, cy, rng.uniform(70, 150), rng.choice(PAL), 0.22)
    # stem / leaf strokes
    ang = rng.uniform(0, 2 * math.pi)
    d.line([(cx, cy), (cx + 160 * math.cos(ang), cy + 160 * math.sin(ang))],
           fill="#2C5F2D", width=10)
for _ in range(90):
    x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(5, 16)
    d.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(["#E89B1C", "#FFFFFF", "#D7402B"]))
d.text((18, H - 34), STAMP, fill="#00000088")
img.save(os.path.join(OUT_DIR, "print_market.png"))

# --- Riverwalk: waves + waveform pulses on indigo ---------------------------
rng = random.Random(313002)
img, d = canvas("#101A3C")
BLUES = ["#2FB6E8", "#4C6FE0", "#9FD8F0", "#FFFFFF", "#1C7293"]
for row in range(14):
    y0 = 40 + row * 82 + rng.uniform(-12, 12)
    color = rng.choice(BLUES)
    pts = []
    amp = rng.uniform(10, 34)
    freq = rng.uniform(1.5, 4.0)
    phase = rng.uniform(0, 6)
    for x in range(0, W + 20, 20):
        pts.append((x, y0 + amp * math.sin(freq * x / W * 2 * math.pi + phase)))
    d.line(pts, fill=color, width=rng.randint(5, 12))
for _ in range(60):  # pulse dots
    x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 9)
    d.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(BLUES))
d.text((18, H - 34), STAMP, fill="#FFFFFF66")
img.save(os.path.join(OUT_DIR, "print_river.png"))

# --- Muralist: big bold shapes on charcoal ----------------------------------
rng = random.Random(313003)
img, d = canvas("#191A1E")
MPAL = ["#8348B5", "#F26A2E", "#1FA98C", "#F2C14E", "#E8E4DA"]
for _ in range(11):
    blob(d, rng, rng.uniform(0, W), rng.uniform(0, H),
         rng.uniform(130, 260), rng.choice(MPAL), 0.35)
for _ in range(26):  # thick strokes
    x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
    ang = rng.uniform(0, 2 * math.pi)
    ln = rng.uniform(150, 420)
    d.line([(x0, y0), (x0 + ln * math.cos(ang), y0 + ln * math.sin(ang))],
           fill=rng.choice(MPAL), width=rng.randint(14, 26))
d.text((18, H - 34), STAMP, fill="#FFFFFF66")
img.save(os.path.join(OUT_DIR, "print_mural.png"))

print("wrote print_market.png, print_river.png, print_mural.png")
