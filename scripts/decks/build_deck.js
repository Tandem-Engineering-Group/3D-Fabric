const pptxgen = require("pptxgenjs");

const ESPRESSO = "2B1B12";
const INK = "2A2119";
const COGNAC = "9A5B33";
const TAN = "C89F6E";
const CREAM = "F5F1EA";
const MUTED = "8A7B6C";
const WHITE = "FFFFFF";
const SOFT = "D8C9B8";

const RENDER = "C:/23 Erika Purse Buisness/designs/CrescentDemo.png";
const PATTERN = "C:/23 Erika Purse Buisness/logs/CrescentDemo_pattern.png";
const NESTED = "C:/23 Erika Purse Buisness/logs/CrescentDemo_nested.png";
const OUT = "C:/23 Erika Purse Buisness/techpack/CrescentDemo_Concept.pptx";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

const H = "Cambria";
const B = "Calibri";

function title(s, text, color) {
  s.addText(text, { x: 0.7, y: 0.45, w: 12.0, h: 0.75, fontFace: H, fontSize: 34,
    bold: true, color: color || INK, margin: 0 });
}
function card(s, x, y, w, h, fill) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.09,
    fill: { color: fill || CREAM }, line: { type: "none" } });
}
function chip(s, x, y, w, text, fill, color) {
  s.addShape("roundRect", { x, y, w, h: 0.34, rectRadius: 0.17,
    fill: { color: fill }, line: { type: "none" } });
  s.addText(text, { x, y, w, h: 0.34, fontFace: B, fontSize: 10.5, bold: true,
    color: color || WHITE, align: "center", valign: "middle", margin: 0, charSpacing: 2 });
}
function numCircle(s, x, y, n, d) {
  const dia = d || 0.5;
  s.addShape("ellipse", { x, y, w: dia, h: dia, fill: { color: COGNAC }, line: { type: "none" } });
  s.addText(String(n), { x, y, w: dia, h: dia, fontFace: H, fontSize: 16, bold: true,
    color: WHITE, align: "center", valign: "middle", margin: 0 });
}

// ---------------------------------------------------------------- S1 cover
let s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("3D-FABRIC PIPELINE  ·  CONCEPT TEST", { x: 0.75, y: 1.15, w: 5.6, h: 0.3,
  fontFace: B, fontSize: 12, color: TAN, charSpacing: 4, margin: 0 });
s.addText("Crescent", { x: 0.7, y: 1.5, w: 5.8, h: 1.3, fontFace: H, fontSize: 64,
  bold: true, color: CREAM, margin: 0 });
s.addText("A curved-bottom shoulder bag, taken from reference photo to 3D concept, sewing pattern, cut files, and cost — in one afternoon.",
  { x: 0.75, y: 2.95, w: 5.3, h: 1.4, fontFace: B, fontSize: 16, color: SOFT, margin: 0 });
chip(s, 0.75, 4.6, 3.1, "DRAFT — NOTHING VERIFIED YET", COGNAC);
s.addText("Prepared by Richard  ·  July 26, 2026", { x: 0.75, y: 6.75, w: 5.5, h: 0.3,
  fontFace: B, fontSize: 11, color: MUTED, margin: 0 });
card(s, 6.6, 0.85, 6.05, 5.8, CREAM);
s.addImage({ path: RENDER, x: 6.8, y: 1.05, w: 5.65, h: 5.4, sizing: { type: "contain", w: 5.65, h: 5.4 } });

// ---------------------------------------------------------------- S2 what it is
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "What it is");
card(s, 0.7, 1.35, 6.1, 5.35);
s.addImage({ path: RENDER, x: 0.9, y: 1.55, w: 5.7, h: 4.95, sizing: { type: "contain", w: 5.7, h: 4.95 } });
const dims = [["11.4\u2033", "wide"], ["6.7\u2033", "tall"], ["3.0\u2033", "deep"]];
dims.forEach((d, i) => {
  s.addText(d[0], { x: 7.15 + i * 1.85, y: 1.45, w: 1.8, h: 0.75, fontFace: H, fontSize: 38,
    bold: true, color: COGNAC, margin: 0 });
  s.addText(d[1], { x: 7.18 + i * 1.85, y: 2.2, w: 1.7, h: 0.3, fontFace: B, fontSize: 12,
    color: MUTED, margin: 0 });
});
s.addText([
  { text: "Top-zip crescent body with a wraparound gusset band", options: { bullet: true, breakLine: true } },
  { text: "Short shoulder strap + long crossbody strap", options: { bullet: true, breakLine: true } },
  { text: "6 cut pieces, 10 mm seam allowance everywhere", options: { bullet: true, breakLine: true } },
  { text: "290 \u00d7 170 \u00d7 75 mm parametric model — every dimension is a slider", options: { bullet: true } },
], { x: 7.15, y: 2.8, w: 5.4, h: 2.2, fontFace: B, fontSize: 14.5, color: INK,
  paraSpaceAfter: 10, margin: 0 });
s.addText("Original silhouette study inspired by a classic crescent shoulder bag. No third-party branding, prints, or hardware — this shape is yours to make 1-of-1.",
  { x: 7.15, y: 5.35, w: 5.4, h: 1.1, fontFace: B, fontSize: 12, italic: true, color: MUTED, margin: 0 });

// ---------------------------------------------------------------- S2b colorways
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "One pattern, any leather");
const RENDERS = "C:/23 Erika Purse Buisness/designs/renders/";
[["brown", "Espresso"], ["black", "Noir"], ["cognac", "Cognac"]].forEach((c, i) => {
  const x = 0.7 + i * 4.25;
  card(s, x, 1.5, 3.95, 4.4);
  s.addImage({ path: RENDERS + "CrescentDemo_" + c[0] + ".png",
    x: x + 0.18, y: 1.68, w: 3.6, h: 3.6, sizing: { type: "contain", w: 3.6, h: 3.6 } });
  s.addText(c[1], { x, y: 5.25, w: 3.95, h: 0.45, fontFace: H, fontSize: 18, bold: true,
    color: INK, align: "center", margin: 0 });
});
s.addText("Same cut files, three colorways — rendered in seconds on the GPU, before a single hide is bought. Launch-quality imagery before launch.",
  { x: 0.7, y: 6.35, w: 12.0, h: 0.6, fontFace: B, fontSize: 14, italic: true,
    color: MUTED, align: "center", margin: 0 });

// ---------------------------------------------------------------- S3 pipeline
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "Photo to factory-ready, automatically");
const steps = [
  ["Concept", "A photo or sketch of the shape you want"],
  ["3D model", "Parametric Blender build — spin it, resize it, re-render it"],
  ["Pattern", "Auto-unfolded to flat pieces, seams at panel edges"],
  ["Nest", "Pieces packed onto a 54\u2033 fabric roll"],
  ["Cost", "Yardage and dollars per bag, instantly"],
  ["Hand-off", "SVG + DXF cut paths + tech pack for the sample maker"],
];
steps.forEach((st, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.7 + col * 4.25, y = 1.5 + row * 2.45;
  card(s, x, y, 3.95, 2.15);
  numCircle(s, x + 0.25, y + 0.25, i + 1);
  s.addText(st[0], { x: x + 0.95, y: 0.27 + y, w: 2.8, h: 0.5, fontFace: H, fontSize: 19,
    bold: true, color: INK, valign: "middle", margin: 0 });
  s.addText(st[1], { x: x + 0.28, y: y + 0.95, w: 3.4, h: 1.05, fontFace: B, fontSize: 13,
    color: INK, margin: 0 });
});
s.addText("This bag: mesh \u2192 tech pack in 5.8 seconds  ·  60 automated tests green  ·  every artifact stamped DRAFT until a human seals it",
  { x: 0.7, y: 6.65, w: 12.0, h: 0.4, fontFace: B, fontSize: 13, italic: true,
    color: MUTED, align: "center", margin: 0 });

// ---------------------------------------------------------------- S4 pattern
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "The pattern — six pieces");
card(s, 0.7, 1.35, 7.15, 5.5);
s.addImage({ path: PATTERN, x: 0.9, y: 1.55, w: 6.75, h: 5.1, sizing: { type: "contain", w: 6.75, h: 5.1 } });
const pieces = [
  ["A", "Gusset band (sides + top)", "95 \u00d7 466 mm"],
  ["B", "Front panel", "310 \u00d7 155 mm"],
  ["C", "Back panel", "310 \u00d7 155 mm"],
  ["D", "Bottom band", "302 \u00d7 95 mm"],
  ["E", "Crossbody strap", "38 \u00d7 1120 mm"],
  ["F", "Shoulder strap (leather section)", "40 \u00d7 176 mm"],
];
pieces.forEach((p, i) => {
  const y = 1.5 + i * 0.62;
  numCircleLabel(s, 8.15, y, p[0]);
  s.addText(p[1], { x: 8.75, y, w: 2.9, h: 0.42, fontFace: B, fontSize: 13, bold: true,
    color: INK, valign: "middle", margin: 0 });
  s.addText(p[2], { x: 11.55, y, w: 1.35, h: 0.42, fontFace: B, fontSize: 11.5,
    color: MUTED, valign: "middle", margin: 0, align: "right" });
});
s.addText("Solid line = cut (includes 10 mm seam allowance)  ·  dashed red = stitch line",
  { x: 8.15, y: 5.5, w: 4.6, h: 0.8, fontFace: B, fontSize: 12, italic: true, color: MUTED, margin: 0 });
function numCircleLabel(sl, x, y, ch) {
  sl.addShape("ellipse", { x, y, w: 0.42, h: 0.42, fill: { color: TAN }, line: { type: "none" } });
  sl.addText(ch, { x, y, w: 0.42, h: 0.42, fontFace: H, fontSize: 13, bold: true,
    color: ESPRESSO, align: "center", valign: "middle", margin: 0 });
}

// ---------------------------------------------------------------- S5 cut files
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "Cut files any shop can run");
card(s, 0.7, 1.35, 5.3, 5.5);
s.addImage({ path: NESTED, x: 0.9, y: 1.55, w: 4.9, h: 5.1, sizing: { type: "contain", w: 4.9, h: 5.1 } });
s.addText("DXF for AutoCAD, Illustrator, and laser cutters", { x: 6.4, y: 1.4, w: 6.2, h: 0.45,
  fontFace: H, fontSize: 20, bold: true, color: INK, margin: 0 });
s.addText([
  { text: "Layered file: CUT (solid), STITCH (dashed), LABEL (piece names) — millimeter units", options: { bullet: true, breakLine: true } },
  { text: "Nested marker: 54\u2033 roll, 11.7\u2033 used per bag \u2192 0.36 yd", options: { bullet: true, breakLine: true } },
  { text: "Same geometry also ships as SVG for Ponoko\u2019s upload flow", options: { bullet: true } },
], { x: 6.4, y: 2.0, w: 6.2, h: 1.9, fontFace: B, fontSize: 14.5, color: INK,
  paraSpaceAfter: 10, margin: 0 });
card(s, 6.4, 4.15, 6.2, 1.5);
s.addText("The nester lays the long straps flat across the roll, so a single bag needs just 11.7 inches of a 54-inch roll (49.7% packed). Batching several bags per marker tightens it further.",
  { x: 6.65, y: 4.35, w: 5.7, h: 1.1, fontFace: B, fontSize: 13, color: INK, margin: 0 });
s.addText("Files: CrescentDemo_cutpaths.dxf  ·  CrescentDemo_pattern.dxf  ·  nested_54in.svg",
  { x: 6.4, y: 6.0, w: 6.2, h: 0.6, fontFace: B, fontSize: 11.5, color: MUTED, margin: 0 });

// ---------------------------------------------------------------- S6 cost
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "What one costs — draft numbers");
const costs = [
  ["$6.43", "CANVAS, PER BAG", "0.36 yd @ $18/yd placeholder pricing, 10% waste factor included"],
  ["$160", "LEATHER, PER BAG", "1 full hide by the tool\u2019s flagged approximation — real usage is a fraction of a side once bags are batched"],
  ["$15\u201325", "HARDWARE, EST.", "Zipper, D-rings, chain accent, magnetic snap — stub BOM, needs real quotes"],
];
costs.forEach((c, i) => {
  const x = 0.7 + i * 4.25;
  card(s, x, 1.5, 3.95, 2.6);
  s.addText(c[0], { x: x + 0.3, y: 1.75, w: 3.4, h: 0.85, fontFace: H, fontSize: 44,
    bold: true, color: COGNAC, margin: 0 });
  s.addText(c[1], { x: x + 0.32, y: 2.6, w: 3.35, h: 0.3, fontFace: B, fontSize: 11,
    bold: true, color: MUTED, charSpacing: 2, margin: 0 });
  s.addText(c[2], { x: x + 0.3, y: 2.95, w: 3.4, h: 1.0, fontFace: B, fontSize: 11.5,
    color: INK, margin: 0 });
});
s.addText("Getting to a physical bag", { x: 0.7, y: 4.5, w: 6, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: INK, margin: 0 });
s.addText([
  { text: "Felt fit-check (Ponoko): tens of dollars — proves shape and proportions", options: { bullet: true, breakLine: true } },
  { text: "Laser-cut leather panels: low hundreds — real material, our assembly", options: { bullet: true, breakLine: true } },
  { text: "Professionally sewn sample (ISAIC, Detroit): by quote — small batch is their mission", options: { bullet: true } },
], { x: 0.7, y: 5.0, w: 11.8, h: 1.5, fontFace: B, fontSize: 14, color: INK,
  paraSpaceAfter: 8, margin: 0 });
s.addText("Every number on this slide is a placeholder in materials.yaml until quoted.",
  { x: 0.7, y: 6.75, w: 11.8, h: 0.35, fontFace: B, fontSize: 12, italic: true, color: MUTED, margin: 0 });

// ---------------------------------------------------------------- S7 make
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "Three ways to make it");
const routes = [
  ["Felt fit-check", "Upload the DXF to Ponoko. Cheap felt, no minimums. Hold the shape in your hands before spending on leather."],
  ["Leather panels", "Laser-cut full-grain panels from the same file — printable with artwork. We assemble and finish locally."],
  ["Sewn sample", "ISAIC in Detroit takes the pattern + tech pack and returns a production-grade sample. Ten minutes from home."],
];
routes.forEach((r, i) => {
  const x = 0.7 + i * 4.25;
  card(s, x, 1.5, 3.95, 3.0);
  numCircle(s, x + 0.28, y7(i), i + 1, 0.55);
  s.addText(r[0], { x: x + 1.0, y: 1.75, w: 2.8, h: 0.55, fontFace: H, fontSize: 19,
    bold: true, color: INK, valign: "middle", margin: 0 });
  s.addText(r[1], { x: x + 0.3, y: 2.5, w: 3.4, h: 1.8, fontFace: B, fontSize: 13,
    color: INK, margin: 0 });
});
function y7() { return 1.72; }
const weeks = [["W1", "Direction: pick silhouettes + materials mood"],
  ["W2", "Select the hero bag, order the felt cut"],
  ["W3", "Felt arrives — adjust, revise same day, order leather"],
  ["W4", "Real sample in progress, shoot content"]];
weeks.forEach((w, i) => {
  const x = 0.7 + i * 3.2;
  s.addText(w[0], { x, y: 5.0, w: 0.75, h: 0.45, fontFace: H, fontSize: 20, bold: true,
    color: COGNAC, margin: 0 });
  s.addText(w[1], { x, y: 5.5, w: 2.85, h: 1.2, fontFace: B, fontSize: 12.5, color: INK, margin: 0 });
});

// ---------------------------------------------------------------- S8 sell
s = pres.addSlide();
s.background = { color: WHITE };
title(s, "How it sells — 1-of-1 by design");
s.addText([
  { text: "Numbered drops: every bag is a 1-of-1 — the brand promise and the manufacturing model are the same sentence", options: { bullet: true, breakLine: true } },
  { text: "Commissions: a client sketch becomes a render in minutes, a pattern the same evening", options: { bullet: true, breakLine: true } },
  { text: "Each bag ships with its story: the render, the pattern, its number", options: { bullet: true, breakLine: true } },
  { text: "Content is in-house: the 3D renders ARE the launch imagery", options: { bullet: true } },
], { x: 0.7, y: 1.6, w: 5.9, h: 3.4, fontFace: B, fontSize: 15, color: INK,
  paraSpaceAfter: 12, margin: 0 });
card(s, 7.0, 1.5, 5.6, 4.35);
s.addText("Example unit economics (draft)", { x: 7.3, y: 1.75, w: 5.0, h: 0.4,
  fontFace: H, fontSize: 17, bold: true, color: INK, margin: 0 });
const rows = [["Leather (batched, realistic)", "$40"], ["Hardware", "$20"],
  ["Sewing / assembly", "$90"], ["Cost of goods", "$150"],
  ["Retail at 3\u00d7", "$450"], ["Gross per bag", "$300"]];
rows.forEach((r, i) => {
  const y = 2.3 + i * 0.56, boldRow = i >= 3;
  s.addText(r[0], { x: 7.3, y, w: 3.6, h: 0.45, fontFace: B, fontSize: boldRow ? 14.5 : 13.5,
    bold: boldRow, color: boldRow ? INK : MUTED, valign: "middle", margin: 0 });
  s.addText(r[1], { x: 11.0, y, w: 1.3, h: 0.45, fontFace: B, fontSize: boldRow ? 15 : 13.5,
    bold: boldRow, color: boldRow ? COGNAC : INK, valign: "middle", align: "right", margin: 0 });
});
s.addText("Draft math with placeholder costs — the pipeline recomputes this per design the moment a real quote lands.",
  { x: 7.0, y: 6.1, w: 5.6, h: 0.75, fontFace: B, fontSize: 11.5, italic: true, color: MUTED, margin: 0 });

// ---------------------------------------------------------------- S9 close
s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("The machine works.", { x: 0.9, y: 1.7, w: 11.5, h: 0.95, fontFace: H,
  fontSize: 48, bold: true, color: CREAM, margin: 0 });
s.addText("Now it\u2019s taste.", { x: 0.9, y: 2.7, w: 11.5, h: 0.95, fontFace: H,
  fontSize: 48, bold: true, color: TAN, margin: 0 });
s.addText([
  { text: "Pick three real silhouettes worth making", options: { bullet: true, breakLine: true } },
  { text: "Order the first felt fit-check from the DXF on this deck", options: { bullet: true, breakLine: true } },
  { text: "Replace draft prices with real quotes — the costs recompute themselves", options: { bullet: true } },
], { x: 0.95, y: 4.1, w: 10.5, h: 1.8, fontFace: B, fontSize: 17, color: SOFT,
  paraSpaceAfter: 12, margin: 0 });
s.addText("3D-Fabric pipeline  ·  all artifacts DRAFT — AI drafts, engineers seal",
  { x: 0.95, y: 6.75, w: 11.0, h: 0.35, fontFace: B, fontSize: 11, color: MUTED, margin: 0 });

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
