"""PhotoPolish — final photo pass over a render via Google's Nano Banana
(Gemini 2.5 Flash Image). Keeps the bag's design and geometry; upgrades
material realism, lighting nuance, and photographic feel. Optionally applies
an artwork file as a printed front panel (the Color-Me-Art mechanic).

  python pipeline/PhotoPolish.py --image render.png --out polished.png
  python pipeline/PhotoPolish.py --image render.png --artwork art.png --out print.png

Requires GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment. Never commit
keys — the repo is public. Exit codes: 0 ok, 2 no key, 1 API/parse failure.
Cost note: roughly $0.04 per output image at 2026 pricing.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-2.5-flash-image"
ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent")

BASE_PROMPT = (
    "This is a 3D product render of an original handbag design. Recreate it as "
    "a photorealistic studio product photograph for an e-commerce listing: "
    "keep the exact same bag design, silhouette, proportions, colorway, "
    "hardware and camera angle, but make the leather grain, stitching, edge "
    "finish, zipper, chain links, soft shadows and reflections look like a "
    "real photographed bag on a seamless studio backdrop. Do not add any "
    "logos, brand names, monograms, or text."
)

ARTWORK_PROMPT = (
    " Additionally: the second image is an artwork print. Apply it as a "
    "printed textile/leather panel covering the bag's front face, following "
    "the panel's curvature and lighting naturally, like a professionally "
    "printed material. Keep the trim, gusset, straps and hardware unchanged."
)


def api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def b64_image(path: Path) -> dict:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {"inline_data": {"mime_type": mime,
                            "data": base64.b64encode(path.read_bytes()).decode()}}


def build_request(image: Path, artwork: Path | None,
                  extra: str | None) -> dict:
    prompt = BASE_PROMPT + (ARTWORK_PROMPT if artwork else "")
    if extra:
        prompt += " " + extra
    parts = [{"text": prompt}, b64_image(image)]
    if artwork:
        parts.append(b64_image(artwork))
    return {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]}}


def extract_image(response: dict) -> bytes:
    for cand in response.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise ValueError(f"no image in response: {json.dumps(response)[:800]}")


def polish(image: Path, out: Path, artwork: Path | None = None,
           extra: str | None = None, model: str = MODEL,
           timeout: int = 180) -> Path:
    key = api_key()
    if not key:
        print("No GEMINI_API_KEY/GOOGLE_API_KEY in environment.\n"
              "Get a key at https://aistudio.google.com/apikey and set it:\n"
              "  setx GEMINI_API_KEY <key>   (new shells)\n"
              "The pipeline works without this step — it is a finishing pass.",
              file=sys.stderr)
        sys.exit(2)
    req = urllib.request.Request(
        ENDPOINT.format(model=model),
        data=json.dumps(build_request(image, artwork, extra)).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:600]
        raise RuntimeError(f"Gemini API HTTP {e.code}: {detail}") from e
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(extract_image(body))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True, help="input render (png/jpg)")
    ap.add_argument("--out", required=True, help="output png")
    ap.add_argument("--artwork", help="optional print artwork to apply to the front panel")
    ap.add_argument("--prompt-extra", help="extra instruction appended to the prompt")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--dry-run", action="store_true",
                    help="print request summary without calling the API")
    args = ap.parse_args()

    image = Path(args.image)
    artwork = Path(args.artwork) if args.artwork else None
    if args.dry_run:
        req = build_request(image, artwork, args.prompt_extra)
        parts = req["contents"][0]["parts"]
        print(json.dumps({"model": args.model, "parts": len(parts),
                          "prompt": parts[0]["text"][:200] + "..."}, indent=2))
        return
    out = polish(image, Path(args.out), artwork, args.prompt_extra, args.model)
    print(f"polished -> {out}")
    print("DRAFT — AI-polished image; verify design fidelity before publishing.")


if __name__ == "__main__":
    main()
