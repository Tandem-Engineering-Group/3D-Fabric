"""Nano Banana polish for every concept in the collection manifest."""
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\23 Erika Purse Buisness")
sys.path.insert(0, str(REPO))
from pipeline.PhotoPolish import polish

manifest = json.loads((REPO / "designs/collection01.json").read_text(encoding="utf-8"))
ok, failed = [], []
for c in manifest["concepts"]:
    slug = c["slug"]
    raw = REPO / f"designs/renders/collection/{slug}_raw.png"
    out = REPO / f"designs/renders/collection/{slug}.png"
    art = REPO / c["art"] if c.get("art") else None
    extra = (f"Colorway lock: keep the body, trim, and hardware colors exactly as "
             f"rendered. Mood: {c['mood']}.")
    try:
        t0 = time.time()
        polish(raw, out, artwork=art, extra=extra)
        ok.append(slug)
        print(f"[polish] {slug} ok ({time.time() - t0:.0f}s)", flush=True)
    except SystemExit:
        raise
    except Exception as e:
        failed.append(slug)
        print(f"[polish] {slug} FAILED: {e}", flush=True)
print(f"[polish] done: {len(ok)} ok, {len(failed)} failed {failed}")
