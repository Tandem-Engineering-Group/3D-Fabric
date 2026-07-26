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

## Environment
- Windows 11, Threadripper, RTX 4080 (16GB VRAM), 256GB RAM. Assume elevated shell.
- Working dir: `C:\23 Erika Purse Buisness` — **path contains spaces; quote every path in
  every command and script.**
- Remote: `https://github.com/Tandem-Engineering-Group/3D-Fabric.git` (public — see Secrets).
- Package managers: winget (apps), uv/pip (Python), git.
- winget flags: `--silent --accept-package-agreements --accept-source-agreements`.
  After installs, refresh PATH in-session before verifying.

## Repo layout
```
/pipeline     Python modules (the product of this repo)
/designs      input sketches/photos/meshes
/patterns     output SVG pattern pieces
/takeoffs     nested layouts + yardage/cost JSON + CSV
/techpack     generated spec sheets (md)
/scripts      blender headless scripts, setup scripts
/vendor       third-party binaries/repos   [gitignored]
/weights      AI model weights             [gitignored]
/logs         run + error logs             [gitignored]
STATUS.md     GREEN/AMBER/RED board — update after every task
BOOTSTRAP.md  the run plan for this session
```

## Conventions (house rules)
- PascalCase for module/class names; snake_case functions; scripts are CLI-first
  (`argparse`), importable second.
- STATUS.md uses GREEN (works, verified) / AMBER (works, caveats) / RED (blocked + why +
  log path). Every component gets a row. No component ships without a smoke test.
- AI drafts, engineers seal: outputs are drafts until a human approves. Mark all generated
  patterns/takeoffs `DRAFT — unverified` in file headers until Richard flips them.
- Yardage math: default fabric width 54 in; leather is per-hide, sheet size configurable.
  Report utilization %, linear yardage, and per-unit material cost given $/yd input.

## Guardrails (hard rules)
- Download only from: official winget sources, github.com, gitlab.com, huggingface.co,
  pypi.org, python.org, blender.org. Nothing else.
- **Never commit weights, vendor binaries, or anything >50MB.** Keep `.gitignore` correct
  before the first push. The repo is public: no secrets, no API keys, no tokens, no
  personal data, no client references — ever.
- No purchases, no account creation, no emails/messages sent, no system settings beyond
  software installs, no files touched outside the working dir (except installs).
- If HuggingFace auth is required and no token is present, mark that model RED and fall
  back to the primitive-mesh path — the pipeline must still complete end-to-end.

## Definition of done for this run
A stranger can clone the repo, read STATUS.md, run one command, and get: a demo tote mesh
unfolded to SVG pattern pieces, nested at 54 in, with a yardage/cost takeoff and a
generated tech pack — all committed, all GREEN.
