# 3D-Fabric

Design-to-pattern-to-takeoff pipeline for a small-batch handbag line.
Sketch or photo in → 3D model → flattened sewing pattern (SVG) → nested cut layout →
material takeoff (yardage + cost) → tech pack.

> **Status:** bootstrapping — see [STATUS.md](STATUS.md) for the live GREEN/AMBER/RED board.

```mermaid
flowchart LR
    A[Sketch / photo] -->|Img2Mesh - TRELLIS 2 / TripoSR| B[3D mesh .glb]
    B2[Existing mesh .glb/.obj] --> C
    B --> C[MeshPrep - cleanup + decimate]
    C --> D[SeamsAndFlatten - seams to sewing pattern]
    D --> E[Pattern pieces SVG - mm units + seam allowance]
    E --> F[Nesting - bottom-left-fill on 54 in sheet]
    F --> G[Takeoff - yardage, utilization, cost per bag]
    E --> H[TechPack - spec sheet md]
    G --> H
```

## Quickstart (once bootstrap completes)

```bash
python run_pipeline.py --mesh "designs/FeltCheckTote.glb" --name FeltCheckTote --width 54 --material canvas
```

Outputs land in `patterns/<name>/`, `takeoffs/<name>/`, and `techpack/<name>.md`.

All generated patterns and takeoffs are stamped `DRAFT — unverified` until a human
approves them. AI drafts, engineers seal.

## Layout

| Path | What |
|------|------|
| `pipeline/` | Python modules (the product) |
| `designs/` | input sketches/photos/meshes |
| `patterns/` | output SVG pattern pieces |
| `takeoffs/` | nested layouts + yardage/cost |
| `techpack/` | generated spec sheets |
| `scripts/` | Blender headless + setup scripts |
| `tests/` | pytest smoke tests |
