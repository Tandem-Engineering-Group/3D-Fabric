const pptxgen = require("pptxgenjs");

const ESPRESSO = "2B1B12";
const INK = "2A2119";
const COGNAC = "9A5B33";
const TAN = "C89F6E";
const CREAM = "F5F1EA";
const MUTED = "8A7B6C";
const WHITE = "FFFFFF";
const SOFT = "D8C9B8";

const R = "C:/23 Erika Purse Buisness/";
const IMG = {
  v1: R + "logs/CrescentDemo_v1_eevee.png",
  v2: R + "designs/renders/CrescentDemo_brown.png",
  polished: R + "designs/renders/CrescentDemo_polished.png",
  artprint: R + "designs/renders/CrescentDemo_artprint.png",
  pattern: R + "logs/CrescentDemo_pattern.png",
  nested: R + "logs/CrescentDemo_nested.png",
  art: R + "designs/artwork/placeholder_print.png",
};
const OUT = R + "techpack/CrescentDemo_InOut.pptx";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
const H = "Cambria";
const B = "Calibri";

function title(s, text, color) {
  s.addText(text, { x: 0.7, y: 0.42, w: 12.0, h: 0.75, fontFace: H, fontSize: 32,
    bold: true, color: color || INK, margin: 0 });
}
function card(s, x, y, w, h, fill) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.09,
    fill: { color: fill || CREAM }, line: { type: "none" } });
}
function imgCard(s, x, y, w, h, path, label) {
  card(s, x, y, w, h + (label ? 0.42 : 0));
  s.addImage({ path, x: x + 0.15, y: y + 0.15, w: w - 0.3, h: h - 0.3,
    sizing: { type: "contain", w: w - 0.3, h: h - 0.3 } });
  if (label) {
    s.addText(label, { x, y: y + h - 0.08, w, h: 0.45, fontFace: H, fontSize: 15,
      bold: true, color: INK, align: "center", margin: 0 });
  }
}

// ------------------------------------------------------------------ S1 cover
let s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("CRESCENT  ·  PIPELINE TEST REPORT", { x: 0.75, y: 1.1, w: 5.6, h: 0.3,
  fontFace: B, fontSize: 12, color: TAN, charSpacing: 4, margin: 0 });
s.addText("In. Out. Better.", { x: 0.7, y: 1.5, w: 5.9, h: 2.2, fontFace: H,
  fontSize: 52, bold: true, color: CREAM, margin: 0 });
s.addText("What we fed the machine, what it spat out, and exactly how the next one gets more real.",
  { x: 0.75, y: 3.35, w: 5.2, h: 1.2, fontFace: B, fontSize: 16, color: SOFT, margin: 0 });
s.addText("Prepared by Richard  ·  July 26, 2026  ·  all outputs DRAFT",
  { x: 0.75, y: 6.75, w: 5.5, h: 0.3, fontFace: B, fontSize: 11, color: MUTED, margin: 0 });
card(s, 6.6, 0.85, 6.05, 5.8, CREAM);
s.addImage({ path: IMG.polished, x: 6.8, y: 1.05, w: 5.65, h: 5.4,
  sizing: { type: "contain", w: 5.65, h: 5.4 } });

// ------------------------------------------------------------------ S2 inputs
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "What went in");
card(s, 0.7, 1.4, 5.9, 2.6);
s.addText("1 · A reference photo", { x: 1.0, y: 1.62, w: 5.3, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: INK, margin: 0 });
s.addText("A classic crescent-body, chain-strap shoulder bag. The branded photo stays on the mood board — we borrow the silhouette language only. No logos, no monogram prints, no third-party hardware marks ever enter the files.",
  { x: 1.0, y: 2.1, w: 5.3, h: 1.7, fontFace: B, fontSize: 13.5, color: INK, margin: 0 });
card(s, 0.7, 4.25, 5.9, 2.6);
s.addText("2 · Fifteen numbers", { x: 1.0, y: 4.47, w: 5.3, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: INK, margin: 0 });
s.addText("290 × 170 × 75 mm body · 20 mm straps · 10 mm seam allowance · 3 colorways · one command:",
  { x: 1.0, y: 4.95, w: 5.3, h: 0.8, fontFace: B, fontSize: 13.5, color: INK, margin: 0 });
s.addText("make_shoulder_bag.py --width-mm 290 --height-mm 170 --depth-mm 75",
  { x: 1.0, y: 5.85, w: 5.3, h: 0.6, fontFace: "Courier New", fontSize: 11.5,
    color: COGNAC, margin: 0 });
card(s, 7.0, 1.4, 5.6, 5.45);
s.addText("3 · The machine", { x: 7.3, y: 1.62, w: 5.0, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: INK, margin: 0 });
s.addText([
  { text: "Blender 5.1 — parametric model, Cycles GPU render (RTX 4080)", options: { bullet: true, breakLine: true } },
  { text: "3D-Fabric pipeline — auto-flatten, nest, cost, tech pack, DXF", options: { bullet: true, breakLine: true } },
  { text: "Nano Banana (Gemini 2.5 Flash Image) — final photo polish", options: { bullet: true, breakLine: true } },
  { text: "60 automated tests keep every stage honest", options: { bullet: true } },
], { x: 7.3, y: 2.15, w: 5.0, h: 2.4, fontFace: B, fontSize: 14, color: INK,
  paraSpaceAfter: 10, margin: 0 });
s.addText("Total human time for this bag: about an hour of direction. Total machine time: minutes.",
  { x: 7.3, y: 5.6, w: 5.0, h: 1.0, fontFace: B, fontSize: 13, italic: true,
    color: MUTED, margin: 0 });

// ------------------------------------------------------------------ S3 output evolution
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "What came out — three passes to real");
imgCard(s, 0.7, 1.45, 3.95, 4.1, IMG.v1, "v1 · flat preview");
imgCard(s, 4.85, 1.45, 3.95, 4.1, IMG.v2, "v2 · path-traced");
imgCard(s, 9.0, 1.45, 3.95, 4.1, IMG.polished, "v3 · photo-polished");
s.addText([
  { text: "v1: geometry proof — honest, and sad. ", options: { breakLine: false } },
  { text: "v2: Cycles GPU, leather shader, chain + zipper, studio light. ", options: { breakLine: false } },
  { text: "v3: Nano Banana finishing — grain, stitching, hang tag, e-commerce feel.", options: {} },
], { x: 0.7, y: 6.15, w: 12.0, h: 0.9, fontFace: B, fontSize: 14, color: INK, margin: 0 });

// ------------------------------------------------------------------ S4 output goods
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "What came out — the factory package");
imgCard(s, 0.7, 1.45, 6.2, 4.6, IMG.pattern, "");
s.addText("6-piece pattern · 10 mm allowance · stitch lines dashed",
  { x: 0.7, y: 6.15, w: 6.2, h: 0.4, fontFace: B, fontSize: 12.5, color: MUTED,
    align: "center", margin: 0 });
const stats = [
  ["0.36 yd", "canvas per bag → $6.43 draft"],
  ["54\u2033 marker", "11.7\u2033 used, straps laid flat by the nester"],
  ["4 file types", "SVG + DXF cut paths + tech pack + JSON costs"],
];
stats.forEach((st, i) => {
  const y = 1.45 + i * 1.15;
  s.addText(st[0], { x: 7.3, y, w: 2.6, h: 0.6, fontFace: H, fontSize: 26, bold: true,
    color: COGNAC, margin: 0 });
  s.addText(st[1], { x: 9.9, y: y + 0.08, w: 2.7, h: 0.9, fontFace: B, fontSize: 12.5,
    color: INK, margin: 0 });
});
card(s, 7.3, 5.0, 5.3, 1.5);
s.addText("Every artifact is stamped DRAFT until a human seals it. Prices are placeholders awaiting real quotes.",
  { x: 7.55, y: 5.2, w: 4.8, h: 1.1, fontFace: B, fontSize: 12.5, italic: true,
    color: INK, margin: 0 });

// ------------------------------------------------------------------ S5 nano banana
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "The finishing pass — Nano Banana");
imgCard(s, 0.7, 1.45, 4.6, 4.4, IMG.v2, "render in");
imgCard(s, 5.5, 1.45, 4.6, 4.4, IMG.polished, "photo out");
s.addText([
  { text: "Keeps design, angle, colorway; adds photographic realism", options: { bullet: true, breakLine: true } },
  { text: "~$0.04 per image, ~15 seconds", options: { bullet: true, breakLine: true } },
  { text: "Caveat: can drift color (espresso → tan here) — lock the colorway in the prompt and verify against the pattern spec", options: { bullet: true, breakLine: true } },
  { text: "Output is marketing DRAFT, never the engineering source of truth", options: { bullet: true } },
], { x: 10.35, y: 1.55, w: 2.6, h: 4.4, fontFace: B, fontSize: 12, color: INK,
  paraSpaceAfter: 9, margin: 0 });

// ------------------------------------------------------------------ S6 the Erika twist
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "The Erika twist — Color Me Art on leather");
imgCard(s, 0.7, 1.45, 3.4, 3.4, IMG.art, "artwork file in");
imgCard(s, 4.5, 1.45, 5.0, 4.9, IMG.artprint, "");
s.addText([
  { text: "Any artwork file drops onto the front panel — printed leather/textile, done at Ponoko or ISAIC", options: { bullet: true, breakLine: true } },
  { text: "The pattern shown is a PLACEHOLDER — awaiting real Color Me Art files in designs/artwork/", options: { bullet: true, breakLine: true } },
  { text: "Detroit-made, Black-owned, every bag a 1-of-1 — the print IS the product strategy", options: { bullet: true, breakLine: true } },
  { text: "Next: a small numbered-drop mockup series from Erika\u2019s actual pieces", options: { bullet: true } },
], { x: 9.8, y: 1.55, w: 3.1, h: 4.9, fontFace: B, fontSize: 12.5, color: INK,
  paraSpaceAfter: 10, margin: 0 });
s.addText("Placeholder pattern generated for this test — not Color Me Art.",
  { x: 0.7, y: 6.55, w: 8.8, h: 0.35, fontFace: B, fontSize: 11, italic: true,
    color: MUTED, margin: 0 });

// ------------------------------------------------------------------ S7 improve the bag
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "How the next one gets more real — the bag");
const bagFixes = [
  ["Construction", "Model the true zipper gusset + interior lining; the pattern then includes facing and lining pieces"],
  ["Stitch detail", "Topstitch lines and edge paint in the 3D model, matching the pattern\u2019s stitch lines"],
  ["Softness", "Cloth-sim slouch pass so leather drapes instead of standing rigid"],
  ["Hardware", "Modeled clips and D-ring connectors where chain meets body; blank embossed hang tag until the brand mark exists"],
  ["Color truth", "Per-colorway material presets locked across render, polish, and materials.yaml"],
  ["Her art", "Real Color Me Art files, print-proofed at Ponoko on felt first"],
];
bagFixes.forEach((f, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.7 + col * 6.2, y = 1.45 + row * 1.75;
  card(s, x, y, 5.9, 1.55);
  s.addText(f[0], { x: x + 0.28, y: y + 0.18, w: 5.3, h: 0.4, fontFace: H, fontSize: 15,
    bold: true, color: COGNAC, margin: 0 });
  s.addText(f[1], { x: x + 0.28, y: y + 0.6, w: 5.35, h: 0.85, fontFace: B,
    fontSize: 12, color: INK, margin: 0 });
});

// ------------------------------------------------------------------ S8 improve the pipeline
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "How the next one gets more real — the machine");
const pipeFixes = [
  ["Batch nesting", "Cut several bags per marker; single-unit 49.7% utilization climbs and cost-per-bag drops"],
  ["Real prices", "Replace materials.yaml placeholders with quoted leather, hardware, and sewing numbers"],
  ["Curated seams", "Designer-placed seam lines via the interactive Blender session instead of auto-seams"],
  ["AI mesh leg", "Stand up TRELLIS.2 (needs VS Build Tools or WSL2) for photo → 3D on real sketches"],
  ["Polish presets", "Color-locked Nano Banana prompts per colorway; batch the whole drop in one run"],
  ["Drop dashboard", "Every design: status, cost, margin — decisions with real numbers"],
];
pipeFixes.forEach((f, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.7 + col * 6.2, y = 1.45 + row * 1.75;
  card(s, x, y, 5.9, 1.55);
  s.addText(f[0], { x: x + 0.28, y: y + 0.18, w: 5.3, h: 0.4, fontFace: H, fontSize: 15,
    bold: true, color: COGNAC, margin: 0 });
  s.addText(f[1], { x: x + 0.28, y: y + 0.6, w: 5.35, h: 0.85, fontFace: B,
    fontSize: 12, color: INK, margin: 0 });
});

// ------------------------------------------------------------------ S9 close
s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("From her sketchbook", { x: 0.9, y: 1.6, w: 11.5, h: 0.9, fontFace: H,
  fontSize: 44, bold: true, color: CREAM, margin: 0 });
s.addText("to a bag on the table.", { x: 0.9, y: 2.55, w: 11.5, h: 0.9, fontFace: H,
  fontSize: 44, bold: true, color: TAN, margin: 0 });
s.addText([
  { text: "Drop real Color Me Art files into designs/artwork/", options: { bullet: true, breakLine: true } },
  { text: "Pick the first drop\u2019s three silhouettes", options: { bullet: true, breakLine: true } },
  { text: "Order the felt fit-check from the DXF — tens of dollars to hold it", options: { bullet: true } },
], { x: 0.95, y: 4.0, w: 10.5, h: 1.7, fontFace: B, fontSize: 17, color: SOFT,
  paraSpaceAfter: 12, margin: 0 });
s.addText("Detroit-made · Black-owned · every bag a 1-of-1 — LFG",
  { x: 0.95, y: 6.2, w: 11.0, h: 0.45, fontFace: H, fontSize: 16, bold: true,
    color: TAN, margin: 0 });
s.addText("3D-Fabric pipeline · all artifacts DRAFT — AI drafts, engineers seal",
  { x: 0.95, y: 6.85, w: 11.0, h: 0.3, fontFace: B, fontSize: 10.5, color: MUTED, margin: 0 });

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
