"""Build the GitHub Pages site from the portal fragment.

portal/index.html is the canonical fragment (also published as a Claude artifact,
which supplies its own document wrapper). This script wraps it into a complete
HTML document at docs/index.html for GitHub Pages.

Usage: python scripts/build_portal_site.py
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Erika purse line — project status, ten-week plan, and the first-purse design brief.">
<title>{title}</title>
</head>
<body>
"""

FOOT = "</body>\n</html>\n"


def build(src: Path, dst: Path) -> None:
    fragment = src.read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>\s*", fragment, re.S)
    title = m.group(1).strip() if m else "Erika — Project Portal"
    body = fragment[m.end():] if m else fragment
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(HEAD.format(title=title) + body + FOOT, encoding="utf-8")
    (dst.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {dst} ({dst.stat().st_size} bytes)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", type=Path, default=ROOT / "portal" / "index.html")
    p.add_argument("--dst", type=Path, default=ROOT / "docs" / "index.html")
    args = p.parse_args()
    build(args.src, args.dst)
