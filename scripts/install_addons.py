"""Install + enable Blender add-ons headless. Run as:

  blender --background --python scripts/install_addons.py

Installs:
  * seams_to_sewing_pattern  (from vendor/blender-seams-to-sewing-pattern)
  * blender_mcp_addon        (from vendor/blender-mcp/addon.py)

Writes logs/install_addons.result.json with what ended up enabled so callers
never parse Blender stdout.
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

import addon_utils
import bpy

REPO = Path(__file__).resolve().parent.parent
VENDOR = REPO / "vendor"
LOGS = REPO / "logs"
LOGS.mkdir(exist_ok=True)
STAGE = LOGS / "addon_staging"
STAGE.mkdir(exist_ok=True)

result = {"enabled": [], "errors": []}


def zip_addon_dir(src: Path, module_name: str) -> Path:
    """Zip a cloned addon repo as <module_name>/ so Blender gets a clean module."""
    zpath = STAGE / f"{module_name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*.py"):
            zf.write(f, f"{module_name}/{f.relative_to(src)}")
    return zpath


def install_and_enable(filepath: Path, module: str):
    bpy.ops.preferences.addon_install(filepath=str(filepath), overwrite=True)
    bpy.ops.preferences.addon_enable(module=module)
    enabled = module in bpy.context.preferences.addons
    if enabled:
        result["enabled"].append(module)
    else:
        result["errors"].append(f"{module}: installed but not enabled")


try:
    seams_src = VENDOR / "blender-seams-to-sewing-pattern"
    install_and_enable(zip_addon_dir(seams_src, "seams_to_sewing_pattern"),
                       "seams_to_sewing_pattern")
except Exception as e:  # noqa: BLE001 — report, don't crash the run
    result["errors"].append(f"seams_to_sewing_pattern: {e!r}")

try:
    mcp_src = VENDOR / "blender-mcp" / "addon.py"
    staged = STAGE / "blender_mcp_addon.py"
    shutil.copyfile(mcp_src, staged)
    install_and_enable(staged, "blender_mcp_addon")
except Exception as e:  # noqa: BLE001
    result["errors"].append(f"blender_mcp_addon: {e!r}")

try:
    bpy.ops.wm.save_userpref()
except Exception as e:  # noqa: BLE001
    result["errors"].append(f"save_userpref: {e!r}")

(LOGS / "install_addons.result.json").write_text(json.dumps(result, indent=2))
print("INSTALL_ADDONS_RESULT:", json.dumps(result))
sys.exit(0 if not result["errors"] else 1)
