# STATUS — 3D-Fabric autonomous run

**Run:** 2026-07-26 · Windows 11 · Threadripper · RTX 4080 SUPER 16GB
Legend: 🟢 GREEN (works, verified) · 🟡 AMBER (works, caveats) · 🔴 RED (blocked) · 🔵 RUNNING

| Task | Component | Status | Notes |
|------|-----------|--------|-------|
| T00 | Repo init, layout, remote, first push | 🟢 GREEN | github.com/Tandem-Engineering-Group/3D-Fabric |
| T01 | Weights: TripoSR 1.7GB, TRELLIS.2-4B 16.2GB, Hunyuan3D-2.1 14.9GB | 🟢 GREEN | All downloaded, all ungated (no HF token needed). `logs/dl-weights.log` |
| T01 | Vendor clones (seams-to-sewing, blender-mcp, ComfyUI, deepnest-next, TripoSR) | 🟢 GREEN | ComfyUI deps deferred — not on critical path |
| T01 | AI venv (.venv-ai): torch 2.13 cu126, CUDA verified | 🟢 GREEN | transformers pinned 4.40.2 (see RUN-REPORT) |
| T02 | Blender | 🟢 GREEN | 4.5.10 LTS installed; 5.1.2 was already present — pipeline uses 5.1, addon verified on both |
| T02 | Inkscape, 7zip, uv | 🟢 GREEN | Inkscape 1.4.4, 7-Zip 26.02, uv 0.11.16 — all verified from fresh shell |
| T03 | Add-ons headless (seams_to_sewing_pattern, blender_mcp) | 🟢 GREEN | Installed+enabled in 4.5 and 5.1; headless `context.area` shim applied at zip time |
| T04 | Nesting engine | 🟢 GREEN | shapely bottom-left-fill; rotations scored by marker growth (straps no longer pin sheet length — ~65% yardage cut on strap-heavy bags). deepnest-next kept in vendor/ as manual QA tool (🟡 vs Deepnest quality) |
| T05 | pipeline/MeshPrep.py | 🟢 GREEN | Blender-headless cleanup/decimate + meshstats.json |
| T05 | pipeline/SeamsAndFlatten.py | 🟢 GREEN | weld+deflake on import; auto-seams: sharp-edge escalation by piece count, boundary always, 89° islands fallback; --max-pieces guard |
| T05 | pipeline/Nesting.py | 🟢 GREEN | pieces.json or SVG in; nested SVG + nesting.json out |
| T05 | pipeline/Takeoff.py | 🟢 GREEN | Yard goods exact; hide math approximation (flagged in output) |
| T05 | pipeline/TechPack.py | 🟢 GREEN | DRAFT-stamped md: overview, piece table, BOM stub, construction stub |
| T05 | pipeline/Img2Mesh.py | 🟢 GREEN | TripoSR backend working end-to-end |
| T06 | FeltCheck Tote demo (proof artifact) | 🟢 GREEN | 7 pieces, 15.54 in @ 83.8% util, 0.47 yd → $8.55/unit, **5.8 s** mesh→tech pack |
| T07 | AI leg: image → mesh → pattern | 🟢 GREEN | TripoSR: 27 s cold / ~10 s warm, ~5.3 GB VRAM; full image→tech pack 17.4 s; 22 pieces @ 60.7% util, 0.94 yd → $16.90/unit draft |
| T07 | TRELLIS.2 / Hunyuan3D Windows runtimes | 🟡 AMBER | Weights present; runtimes need compiled CUDA exts and no MSVC linker on box — TripoSR is the working leg |
| T08 | run_pipeline.py + README | 🟢 GREEN | One command, both input modes; 60 pytest green |
| + | pipeline/ExportDXF.py (AutoCAD/laser cut paths) | 🟢 GREEN | Layered DXF, mm units; 2 tests |
| + | pipeline/PhotoPolish.py (Nano Banana finishing) | 🟢 GREEN | Gemini 2.5 Flash Image; key from env (never committed); color-drift caveat noted |
| T09 | Close-out | 🟢 GREEN | See RUN-REPORT.md |

## Test suite
`pytest tests/ -q` → **60 passed** (Blender-dependent tests run for real on this box; they skip cleanly where Blender/addon is absent).

## Machine facts
winget 1.29 · git 2.54 · Python 3.13.12 + 3.12 · gh 2.94 (authed) · Blender 4.5.10 + 5.1.2 · disk free ~1.5 TB
