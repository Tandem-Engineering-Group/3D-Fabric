# RUN-REPORT — 2026-07-26 autonomous bootstrap

## What got done
Everything in BOOTSTRAP v2, T00–T09. The definition of done is met: clone the repo,
read STATUS.md, run one command, get a demo tote unfolded to SVG pattern pieces,
nested at 54 in, with a yardage/cost takeoff and a tech pack — all committed, all GREEN.

Two proof artifacts:

| Design | Input | Pieces | Sheet used (54 in) | Utilization | Yardage | Draft cost | Wall time |
|--------|-------|--------|--------------------|-------------|---------|-----------|-----------|
| FeltCheckTote | parametric mesh | 7 | 22.44 in | 58.2% | 0.69 yd | $12.34 | 5.8 s |
| TestPurse | single image (AI) | 22 | 30.72 in | 60.7% | 0.94 yd | $16.90 | 17.4 s |

TripoSR image→mesh: 27 s cold / ~10 s warm, ~5.3 GB VRAM on the RTX 4080 SUPER.

## Decisions and fixes worth knowing about
- **Public-repo hygiene:** business-plan PDF and all `*.pdf` are gitignored; commits use
  the repo-local noreply identity. Weights/vendor/logs never committed.
- **Blender:** 5.1.2 was already on the box; 4.5 LTS added via winget. Pipeline
  resolves the newest install (`BLENDER_EXE` overrides). Add-on verified on both.
- **Headless shims:** the seams add-on's `context.area.tag_redraw()` crashes under
  `--background`; patched automatically when `install_addons.py` builds the zip.
- **glTF drops seam marks**, and splits vertices wherever normals differ. Flatten
  therefore welds coincident verts on import, drops floater shells, then auto-seams:
  sharp edges at the lowest threshold (40/60/75°) whose resulting piece count is
  sewable (≤24), boundary edges always, Smart-UV islands (89°) as smooth-blob
  fallback, and a `--max-pieces` guard that fails loudly instead of emitting confetti.
- **TripoSR on Windows/py3.12:** torchmcubes (needs CUDA compiler) replaced by a
  pymcubes shim in the *local* vendor copy; `xatlas`+`moderngl` installed;
  `transformers==4.40.2` + `tokenizers==0.19.1` pinned (the checkpoint predates the
  transformers 5.x ViT key rename; 4.35 is uninstallable on py3.12 — no cp312
  tokenizers wheels).

## AMBER / known limits
- **TRELLIS.2-4B & Hunyuan3D-2.1:** weights downloaded (31 GB), runtimes not stood up —
  both need compiled CUDA extensions and there is no MSVC linker on this box
  (`link.exe not found`). Options: install VS Build Tools, use WSL2, or hunt prebuilt
  wheels. TripoSR carries the AI leg meanwhile.
- **AI pattern quality:** a raw image→mesh blob flattens into ~22 draft pieces — proof
  of mechanics, not a sewable pattern. Real designs want curated seams (`--seams`
  edge JSON, or interactive via the installed blender-mcp addon) on a cleaned mesh.
- **Hide (leather) takeoff** is a flagged approximation (area-based, 0.75 packing
  assumption); yard goods math is exact from the nested layout.
- **Nesting** is greedy bottom-left-fill — good for estimates; deepnest-next sits in
  vendor/ for manual comparisons on production layouts.
- **materials.yaml prices are placeholders** awaiting real vendor quotes.
- Inkscape/7zip/uv winget installs were still finishing at close (not on critical path).

## Recommended next session
1. Curated-seam workflow: seams.json authoring guide + blender-mcp interactive session;
   piece naming (front/gusset/strap) instead of piece-N.
2. Ponoko-ready SVG export profile (their template sizes, stroke conventions) — the
   plan's felt fit-check route.
3. Leather hide sheet shapes + real hide nesting.
4. Grainline arrows + piece metadata on the pattern sheet.
5. TRELLIS.2 runtime via VS Build Tools or WSL2 (16 GB VRAM is tight for the 4B — test).
6. Parametric silhouette library (hobo, crossbody, clutch) alongside make_tote.py.
7. Real material prices in materials.yaml; verify the $12.34 tote number against a
   physical felt cut quote.
