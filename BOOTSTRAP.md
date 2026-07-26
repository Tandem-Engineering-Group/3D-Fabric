# BOOTSTRAP.md — Autonomous Run Plan (v2, revised 2026-07-26 with verified facts)

Execute top to bottom. Rules of engagement are in CLAUDE.md (never block, commit+push
after every task, quote all paths, headless Blender only). Each task has an acceptance
check — a task is GREEN only when its check passes.

Changes from v1: models verified ungated (Hunyuan3D needs NO token — queued third);
TripoSR (1.7GB) added as Windows-safe Img2Mesh fallback and downloads first; Python/git/gh
already installed; GitHub repo already existed (empty) — pushed; business-plan PDF is
local-only (public repo carries no personal data).

## T00 — Repo init & status board ✅
Done: git init (repo-local noreply identity), layout, .gitignore, STATUS.md, remote
`Tandem-Engineering-Group/3D-Fabric`, pushed main.
**Check:** repo visible on GitHub with STATUS.md rendered.

## T01 — Long downloads in background ✅ started
One sequential background job (avoids bandwidth contention), log `logs/dl-weights.log`:
1. **stabilityai/TripoSR** (1.7GB) → `weights/triposr/` — small, lands first, reliably
   runs on Windows; guarantees T07 has a working model.
2. **microsoft/TRELLIS.2-4B** (16.2GB, MIT) → `weights/trellis2/` — primary quality path.
3. **tencent/Hunyuan3D-2.1** (14.9GB) → `weights/hunyuan3d/` — verified ungated.
Also background: clone seams-to-sewing-pattern, blender-mcp, ComfyUI, deepnest-next into
`vendor/` (`logs/clone-vendor.log`). ComfyUI dep install deferred until needed — it is not
on the critical path.
**Check:** downloads running; sizes growing; completion noted in STATUS.md.

## T02 — Core installs (winget, silent) ✅ started
Blender **4.5 LTS**, Inkscape, 7zip via winget (background, `logs/install-apps.log`);
`pip install uv`. Git 2.54, Python 3.13/3.12, gh 2.94 already present — skip those.
Blender lands at `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`; always
call by full quoted path.
**Check:** `& blender.exe --version`, `inkscape --version`, `uv --version` succeed.

## T03 — Blender add-on install (headless)
From `vendor/blender-seams-to-sewing-pattern`: zip the addon dir if needed; install +
enable via `blender --background --python scripts/install_addons.py` (uses
`bpy.ops.preferences.addon_install/addon_enable` + `wm.save_userpref`). Same for
`vendor/blender-mcp/addon.py` (for later interactive use — do NOT rely on it this run).
Fallback if the artyredd fork fails on 4.5: original upstream repo, or pin Blender 4.2 LTS.
**Check:** headless Blender lists both add-ons enabled.

## T04 — Nesting engine
Primary path is our own `pipeline/Nesting.py`: bottom-left-fill heuristic with shapely
(rotation set 0/90/180/270, configurable step), good enough for takeoff estimates.
`uv pip install shapely svgpathtools svgwrite pyyaml pytest` into a project venv.
deepnest-next stays in `vendor/` as a reference/manual-QA tool only (AMBER vs Deepnest
quality is acceptable — note it).
**Check:** given 3 test polygons, produces a nested SVG + utilization % on a 54 in sheet.

## T05 — Pipeline modules (the real work)
Contracts first: `pipeline/common.py` defines the piece JSON schema, SVG conventions
(units = mm, one `<g id="piece-N">` per piece, label + grainline metadata), and the
Blender subprocess wrapper. Then build CLI-first modules in `/pipeline`, each with
`--help` and a pytest smoke test in `/tests`:
- `MeshPrep.py` — import glb/obj → cleanup (merge verts, recalc normals, non-manifold
  report JSON), decimate to target density. (Blender headless subprocess.)
- `SeamsAndFlatten.py` — apply seam markings (edge-group JSON or auto-UV fallback), run
  Seams-to-Sewing-Pattern, export per-piece SVG with labels + seam allowance (default
  10 mm) into `/patterns/<design>/`.
- `Nesting.py` — pieces SVG → nested layout SVG at given sheet width; utilization %,
  linear inches/yards.
- `Takeoff.py` — nesting output + `materials.yaml` → cost JSON + CSV into
  `/takeoffs/<design>/`.
- `TechPack.py` — mesh stats + pieces + takeoff → `techpack/<design>.md` (dims, piece
  list, materials, hardware BOM stub, construction notes stub, DRAFT header).
- `Img2Mesh.py` — image → glb via TRELLIS.2 (fallback TripoSR, then Hunyuan3D) from
  `weights/`. If no weights ready, exit with clear message; pipeline continues via
  `--mesh`.
**Check:** each module runs standalone on test data; pytest green.

## T06 — End-to-end demo: the FeltCheck Tote
No AI dependency: parametric tote via `scripts/make_tote.py` (Blender headless:
body panels, gusset, straps, marked seams), then the full chain:
mesh → SeamsAndFlatten → Nesting (54 in) → Takeoff ($18/yd canvas placeholder) →
TechPack. Commit all outputs. This is the proof artifact.
**Check:** `/patterns/FeltCheckTote/*.svg`, `/takeoffs/FeltCheckTote/takeoff.json`
(yardage + utilization + cost), `/techpack/FeltCheckTote.md` all exist; SVG parses via
svgpathtools and opens clean in Inkscape.

## T07 — AI leg (only if T01 has at least one model down)
Run `Img2Mesh.py` on `designs/test-purse.jpg` (render the T06 tote to an image if no
photo present) → glb → same chain end to end. Record VRAM + timing in STATUS.md.
Windows reality check: TRELLIS/Hunyuan need custom CUDA extensions that often fail to
build on Windows — TripoSR is the guaranteed leg; mark others AMBER/RED honestly.
**Check:** second design folder fully populated from an image input.

## T08 — One-command entry point
`run_pipeline.py --image X | --mesh Y --name Z [--width 54] [--material canvas]` chains
everything. Finish `README.md`: what this is, quickstart, mermaid pipeline diagram,
status badge conventions.
**Check:** fresh-shell run reproduces T06 outputs.

## T09 — Close out
Final STATUS.md sweep (every row GREEN/AMBER/RED + one-line note + log links), write
`logs/RUN-REPORT.md` + commit a public-safe `RUN-REPORT.md` summary: what got done,
what's RED and exactly why, VRAM/timing numbers, recommended next-session tasks. Push.

## If time remains
Priority order: (1) auto-seam heuristics (curvature-based seam suggestion),
(2) leather hide sheet shapes for Nesting, (3) Ponoko upload-ready SVG profile
(their template sizes P1/P2/P3), (4) piece labeling/grainline arrows on patterns,
(5) parametric silhouette library (tote, hobo, crossbody, clutch) as Python generators.
