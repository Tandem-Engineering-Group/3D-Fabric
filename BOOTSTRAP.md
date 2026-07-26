# BOOTSTRAP.md — Autonomous Run Plan

Execute top to bottom. Rules of engagement are in CLAUDE.md (never block, commit+push
after every task, quote all paths, headless Blender only). Each task has an acceptance
check — a task is GREEN only when its check passes.

## T00 — Repo init & status board
Init git in `"C:\23 Erika Purse Buisness"`, create the layout from CLAUDE.md, write
`.gitignore` (weights/, vendor/, logs/, __pycache__, *.blend1, *.zip, *.safetensors,
*.ckpt, *.pth), seed STATUS.md with every task below as a row (all pending), add remote
`https://github.com/Tandem-Engineering-Group/3D-Fabric.git`, first commit, push `main`.
**Check:** repo visible on GitHub with STATUS.md rendered.

## T01 — Start long downloads in background (do this before anything else)
1. `pip install -U "huggingface_hub[cli]"` (or uv tool) and start a background download of
   **TRELLIS.2-4B** (microsoft, MIT — ungated) into `weights/trellis2/`. Log to
   `logs/dl-trellis.log`.
2. If a HF token exists in env, also queue **tencent/Hunyuan3D-2.1** into
   `weights/hunyuan3d/`; if not, skip and note AMBER (fallback path covers it).
3. Clone ComfyUI into `vendor/ComfyUI` and start its Python deps install in background.
**Check:** downloads running; sizes growing; PIDs noted in STATUS.md.

## T02 — Core installs (winget, silent)
Blender LTS, Inkscape, Git (verify), Python 3.12, 7zip. Then `pip install uv`. Refresh
PATH; record every version in STATUS.md.
**Check:** `blender --version`, `inkscape --version`, `python --version`, `uv --version`
all succeed from a fresh shell.

## T03 — Blender add-on install (headless)
Clone `artyredd/blender-seams-to-sewing-pattern` into `vendor/`; zip if needed; install +
enable via `blender --background --python scripts/install_addons.py` (uses
`bpy.ops.preferences.addon_install/addon_enable` + `wm.save_userpref`). Also clone
`ahujasid/blender-mcp` into `vendor/` and install its `addon.py` the same way (for later
interactive use — do NOT rely on it this run).
**Check:** headless Blender lists both add-ons enabled.

## T04 — Nesting engine
Clone/download **deepnest-next** release into `vendor/deepnest`. Regardless of GUI app
success, implement `pipeline/Nesting.py` as the automatable path: `pip install svgnest-py
shapely svgpathtools` (if svgnest-py unavailable, implement bottom-left-fill heuristic
with shapely — good enough for takeoff estimates; note AMBER vs Deepnest quality).
**Check:** given 3 test polygons, produces a nested SVG + utilization % on a 54 in sheet.

## T05 — Pipeline modules (the real work)
Build CLI-first modules in `/pipeline`, each with `--help` and a pytest smoke test:
- `MeshPrep.py` — import glb/obj, cleanup (merge verts, recalc normals, non-manifold
  report), decimate to target density. (Blender headless wrapper.)
- `SeamsAndFlatten.py` — apply seam markings (accept edge-group JSON or auto-UV fallback),
  run Seams-to-Sewing-Pattern, export per-piece SVG with piece labels + seam allowance
  param (default 10 mm) into `/patterns/<design>/`.
- `Nesting.py` — pieces SVG → nested layout SVG at given sheet width; outputs
  utilization %, linear inches/yards.
- `Takeoff.py` — nesting output + `materials.yaml` ($/yd or $/hide) → cost JSON + CSV into
  `/takeoffs/<design>/`.
- `TechPack.py` — mesh stats + pattern pieces + takeoff → `techpack/<design>.md` (dims,
  piece list, materials, hardware BOM stub, construction notes stub, DRAFT header).
- `Img2Mesh.py` — wrapper that calls TRELLIS 2 (or Hunyuan3D) from `weights/` on an input
  image → glb. If weights not ready, exits with clear message; pipeline continues via
  `--mesh` input instead.
**Check:** each module runs standalone on test data; pytest green.

## T06 — End-to-end demo: the FeltCheck Tote
No AI dependency: build a parametric tote in Blender headless (primitives: body panels,
gusset, straps), then run the full chain:
mesh → SeamsAndFlatten → Nesting (54 in) → Takeoff (use placeholder $18/yd canvas) →
TechPack. Commit all outputs. This is the proof artifact.
**Check:** `/patterns/FeltCheckTote/*.svg`, `/takeoffs/FeltCheckTote/takeoff.json` (with
yardage + utilization + cost), `/techpack/FeltCheckTote.md` all exist and open clean in
Inkscape (validate SVG parses via svgpathtools).

## T07 — AI leg (only if T01 finished)
Run `Img2Mesh.py` on `designs/test-purse.jpg` (generate a simple test image locally if
none present — a rendered screenshot of the T06 tote is fine) → glb → run the same chain
end to end. Record VRAM use + timing in STATUS.md.
**Check:** second design folder fully populated from an image input.

## T08 — One-command entry point
`run_pipeline.py --image X | --mesh Y --name Z [--width 54] [--material canvas]` chains
everything. Add `README.md`: what this is, quickstart, pipeline diagram (mermaid), status
badge conventions.
**Check:** fresh-shell run of the command reproduces T06 outputs.

## T09 — Close out
Final STATUS.md sweep (every row GREEN/AMBER/RED + one-line note + log links), write
`logs/RUN-REPORT.md`: what got done, what's RED and exactly why, VRAM/timing numbers,
recommended next session tasks. Commit, push, done.

## If time remains
Priority order: (1) auto-seam heuristics (curvature-based seam suggestion),
(2) leather hide sheet shapes for Nesting, (3) Ponoko upload-ready SVG profile
(their template sizes P1/P2/P3), (4) piece labeling/grainline arrows on patterns,
(5) parametric silhouette library (tote, hobo, crossbody, clutch) as Blender geo-node or
python generators.
