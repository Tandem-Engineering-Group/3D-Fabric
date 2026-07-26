# CLAUDE.md — 3D-Fabric

## Mission
Sketch/photo → 3D purse model → flattened 2D sewing pattern (SVG) → nested cut layout →
material takeoff (yardage + cost) → tech pack. Serves the Erika purse line. One concern,
one repo: this repo owns the design-to-pattern-to-takeoff pipeline. Branding, e-commerce,
and vendor ordering live elsewhere.

## Operating mode: AUTONOMOUS RUN
The owner (Richard) is away. Do not stop to ask questions. Work through BOOTSTRAP.md top
to bottom, then continue improving until context/tasks are exhausted.

- **Never block.** If a task fails after 2 retry attempts, mark it RED in STATUS.md, write
  the error to `logs/`, and move to the next task.
- **Commit + push constantly.** After every completed task: `git add -A && git commit` with
  a clear message, `git push`. Richard reviews from his phone via GitHub — the repo IS the
  status channel. Never force-push. Never rewrite history.
- **Prefer headless.** Drive Blender via `blender --background --python <script>` (or
  `--python-expr`), never the GUI. The blender-mcp GUI socket is for interactive sessions
  later — do not depend on it in this run.
- **Downloads first, thinking second.** Anything large (model weights, ComfyUI) starts as a
  background job immediately so the clock runs while other work proceeds.

## Environment (verified 2026-07-26)
- Windows 11 Pro, Threadripper, RTX 4080 SUPER (16GB VRAM), 256GB RAM, ~1.6TB free disk.
- Working dir: `C:\23 Erika Purse Buisness` — **path contains spaces; quote every path in
  every command and script.**
- Remote: `https://github.com/Tandem-Engineering-Group/3D-Fabric.git` (public — see
  Guardrails). `gh` CLI is authenticated.
- Git identity is repo-local (`rlettsBubs@users.noreply.github.com`). **Never commit with a
  personal/work email — the repo is public.**
- Python 3.13 (default) and 3.12 both preinstalled. Blender 4.5 LTS via winget installs to
  `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe` — scripts must use the full
  quoted path, never assume PATH.
- AI weights (all ungated on HuggingFace as of 2026-07, no token needed):
  `microsoft/TRELLIS.2-4B` (primary, 16GB), `stabilityai/TripoSR` (small fallback that
  reliably runs on Windows), `tencent/Hunyuan3D-2.1` (secondary).
- Package managers: winget (apps), uv/pip (Python), git.
- winget flags: `--silent --accept-package-agreements --accept-source-agreements`.
  After installs, refresh PATH in-session before verifying.

## Repo layout
```
/pipeline     Python modules (the product of this repo)
/designs      input sketches/photos/meshes
/patterns     output SVG pattern pieces        /patterns/<design>/
/takeoffs     nested layouts + yardage/cost    /takeoffs/<design>/
/techpack     generated spec sheets (md)
/scripts      blender headless scripts, setup scripts
/tests        pytest smoke tests
/vendor       third-party binaries/repos   [gitignored]
/weights      AI model weights             [gitignored]
/logs         run + error logs             [gitignored]
STATUS.md     GREEN/AMBER/RED board — update after every task
BOOTSTRAP.md  the run plan for this session
materials.yaml  material prices/widths used by Takeoff
```

## Conventions (house rules)
- PascalCase for module/class names; snake_case functions; scripts are CLI-first
  (`argparse`), importable second.
- Blender-dependent code lives behind a subprocess boundary: pipeline modules call
  `blender --background --python scripts/<x>.py -- <args>`; JSON in/out via files, never
  parse Blender's stdout chatter.
- STATUS.md uses GREEN (works, verified) / AMBER (works, caveats) / RED (blocked + why +
  log path) / RUNNING / PENDING. Every component gets a row. No component ships without a
  smoke test.
- AI drafts, engineers seal: outputs are drafts until a human approves. Mark all generated
  patterns/takeoffs `DRAFT — unverified` in file headers until Richard flips them.
- Yardage math: default fabric width 54 in; leather is per-hide, sheet size configurable.
  Report utilization %, linear yardage, and per-unit material cost given $/yd input.
- Units: pattern SVGs are in **millimeters** (1 SVG user unit = 1 mm); yardage reported in
  inches/yards for US vendors. Seam allowance default 10 mm, parameterized everywhere.

## Guardrails (hard rules)
- Download only from: official winget sources, github.com, gitlab.com, huggingface.co,
  pypi.org, python.org, blender.org. Nothing else.
- **Never commit weights, vendor binaries, or anything >50MB.** Keep `.gitignore` correct
  before every push. The repo is public: no secrets, no API keys, no tokens, no personal
  data, no client references — ever. Business-plan PDFs and personal docs stay local
  (`*.pdf` is gitignored).
- No purchases, no account creation, no emails/messages sent, no system settings beyond
  software installs, no files touched outside the working dir (except installs).
- If a model download or install fails twice, mark it RED and fall back — the pipeline
  must still complete end-to-end via the primitive-mesh path (`--mesh` input).

## Definition of done for this run
A stranger can clone the repo, read STATUS.md, run one command, and get: a demo tote mesh
unfolded to SVG pattern pieces, nested at 54 in, with a yardage/cost takeoff and a
generated tech pack — all committed, all GREEN.
