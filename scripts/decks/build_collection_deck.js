const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ESPRESSO = "2B1B12";
const INK = "2A2119";
const COGNAC = "9A5B33";
const TAN = "C89F6E";
const CREAM = "F5F1EA";
const MUTED = "8A7B6C";
const WHITE = "FFFFFF";
const SOFT = "D8C9B8";

const REPO = "C:/23 Erika Purse Buisness";
const manifest = JSON.parse(fs.readFileSync(REPO + "/designs/collection01.json", "utf8"));
const OUT = REPO + "/techpack/Collection01_Lookbook.pptx";

function img(slug) {
  const polished = `${REPO}/designs/renders/collection/${slug}.png`;
  return fs.existsSync(polished)
    ? polished : `${REPO}/designs/renders/collection/${slug}_raw.png`;
}
function cost(slug) {
  try {
    const t = JSON.parse(fs.readFileSync(`${REPO}/takeoffs/${slug}/takeoff.json`, "utf8"));
    return { yd: t.linear_yd_per_unit, usd: t.material_cost_per_unit_usd };
  } catch (e) { return null; }
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
const H = "Cambria";
const B = "Calibri";

function card(s, x, y, w, h, fill) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.09,
    fill: { color: fill || CREAM }, line: { type: "none" } });
}

// ----------------------------------------------------------------- cover
let s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("COLLECTION 01 · CONCEPT LOOKBOOK · DRAFT", { x: 0.75, y: 1.05, w: 6.0,
  h: 0.3, fontFace: B, fontSize: 12, color: TAN, charSpacing: 4, margin: 0 });
s.addText("Ten for the D", { x: 0.7, y: 1.45, w: 6.2, h: 1.2, fontFace: H,
  fontSize: 56, bold: true, color: CREAM, margin: 0 });
s.addText("One silhouette, ten voices — Detroit streets, Erika\u2019s eye, Color Me Art\u2019s color. Every concept rendered, polished, and priced by the machine the same hour it was named.",
  { x: 0.75, y: 2.8, w: 5.4, h: 1.5, fontFace: B, fontSize: 15, color: SOFT, margin: 0 });
s.addText("Prints are placeholders until real Color Me Art files land. All prices DRAFT.",
  { x: 0.75, y: 6.7, w: 6.0, h: 0.4, fontFace: B, fontSize: 10.5, color: MUTED, margin: 0 });
card(s, 6.7, 0.8, 5.95, 5.9, CREAM);
s.addImage({ path: img("the-313"), x: 6.9, y: 1.0, w: 5.55, h: 5.5,
  sizing: { type: "contain", w: 5.55, h: 5.5 } });

// ----------------------------------------------------------------- input slide
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("It started with one photo", { x: 0.7, y: 0.45, w: 12.0, h: 0.7,
  fontFace: H, fontSize: 32, bold: true, color: INK, margin: 0 });
card(s, 0.7, 1.4, 6.4, 5.4);
s.addImage({ path: REPO + "/designs/renders/collection/input_silhouette.png",
  x: 0.9, y: 1.6, w: 6.0, h: 5.0, sizing: { type: "contain", w: 6.0, h: 5.0 } });
s.addText("What we took", { x: 7.5, y: 1.45, w: 5.1, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: COGNAC, margin: 0 });
s.addText([
  { text: "The crescent profile and its proportions", options: { bullet: true, breakLine: true } },
  { text: "The chain-into-leather strap rhythm", options: { bullet: true, breakLine: true } },
  { text: "The top-zip sweep and hardware warmth", options: { bullet: true } },
], { x: 7.5, y: 1.95, w: 5.1, h: 1.6, fontFace: B, fontSize: 13.5, color: INK,
  paraSpaceAfter: 8, margin: 0 });
s.addText("What we left behind", { x: 7.5, y: 3.75, w: 5.1, h: 0.4, fontFace: H,
  fontSize: 18, bold: true, color: COGNAC, margin: 0 });
s.addText([
  { text: "The logos, the monogram, the brand hardware — trademarks are theirs; the reference photo stays out of our public files", options: { bullet: true, breakLine: true } },
  { text: "What replaces them: Erika’s art, Detroit’s stories, a numbered 1-of-1 drop model", options: { bullet: true } },
], { x: 7.5, y: 4.25, w: 5.1, h: 2.2, fontFace: B, fontSize: 13.5, color: INK,
  paraSpaceAfter: 8, margin: 0 });

// ----------------------------------------------------------------- process slide
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("The whole process, one loop", { x: 0.7, y: 0.45, w: 12.0, h: 0.7,
  fontFace: H, fontSize: 32, bold: true, color: INK, margin: 0 });
const steps = [
  ["Reference", "One photo becomes geometry — shape only, nothing branded"],
  ["Parametric bag", "A Blender model where every dimension is a dial"],
  ["Ten voices", "One manifest file names each concept: size, leather, hardware, print, story"],
  ["Render + polish", "GPU studio shots, then a Nano Banana photo pass (~$0.04/image)"],
  ["Pattern + price", "Auto-flattened pieces, nested, costed — DXF cut files included"],
  ["This lookbook", "Deck and reel build themselves from the same manifest"],
];
steps.forEach((st, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.7 + col * 4.25, y = 1.45 + row * 2.5;
  card(s, x, y, 3.95, 2.25);
  s.addShape("ellipse", { x: x + 0.25, y: y + 0.22, w: 0.5, h: 0.5,
    fill: { color: COGNAC }, line: { type: "none" } });
  s.addText(String(i + 1), { x: x + 0.25, y: y + 0.22, w: 0.5, h: 0.5,
    fontFace: H, fontSize: 16, bold: true, color: WHITE, align: "center",
    valign: "middle", margin: 0 });
  s.addText(st[0], { x: x + 0.92, y: y + 0.24, w: 2.9, h: 0.5, fontFace: H,
    fontSize: 18, bold: true, color: INK, valign: "middle", margin: 0 });
  s.addText(st[1], { x: x + 0.28, y: y + 0.95, w: 3.4, h: 1.2, fontFace: B,
    fontSize: 12.5, color: INK, margin: 0 });
});
s.addText("10 concepts · 10 patterns · 10 draft prices · one afternoon · every artifact stamped DRAFT",
  { x: 0.7, y: 6.75, w: 12.0, h: 0.4, fontFace: B, fontSize: 13, italic: true,
    color: MUTED, align: "center", margin: 0 });

// ----------------------------------------------------------------- 5 spreads x 2 concepts
const cs = manifest.concepts;
for (let i = 0; i < cs.length; i += 2) {
  const s2 = pres.addSlide();
  s2.background = { color: WHITE };
  [cs[i], cs[i + 1]].forEach((c, k) => {
    if (!c) return;
    const x = 0.55 + k * 6.25;
    card(s2, x, 0.5, 5.95, 4.15);
    s2.addImage({ path: img(c.slug), x: x + 0.18, y: 0.68, w: 5.6, h: 3.8,
      sizing: { type: "contain", w: 5.6, h: 3.8 } });
    s2.addText(c.name, { x, y: 4.8, w: 4.3, h: 0.5, fontFace: H, fontSize: 23,
      bold: true, color: INK, margin: 0 });
    const co = cost(c.slug);
    if (co) {
      s2.addText(`$${co.usd} draft`, { x: x + 4.35, y: 4.86, w: 1.6, h: 0.4,
        fontFace: H, fontSize: 15, bold: true, color: COGNAC, align: "right", margin: 0 });
    }
    s2.addText(c.changes, { x, y: 5.32, w: 5.95, h: 0.62, fontFace: B, fontSize: 11.5,
      italic: true, color: MUTED, margin: 0 });
    s2.addText(c.speaks, { x, y: 5.98, w: 5.95, h: 1.1, fontFace: B, fontSize: 13,
      color: INK, margin: 0 });
  });
}

// ----------------------------------------------------------------- lineup table
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("The loop, closed — every concept priced the moment it existed",
  { x: 0.7, y: 0.45, w: 12.0, h: 0.7, fontFace: H, fontSize: 28, bold: true,
    color: INK, margin: 0 });
const header = ["Concept", "Size (W\u00d7H\u00d7D mm)", "Hardware", "Print", "Yd/bag", "Canvas $ draft"];
const widths = [3.3, 2.6, 1.5, 1.7, 1.3, 1.6];
let cx = 0.7;
header.forEach((h2, j) => {
  s.addText(h2, { x: cx, y: 1.35, w: widths[j], h: 0.4, fontFace: B, fontSize: 12,
    bold: true, color: COGNAC, margin: 0 });
  cx += widths[j];
});
cs.forEach((c, i) => {
  const y = 1.8 + i * 0.5;
  const co = cost(c.slug);
  const row = [c.name, `${c.w} \u00d7 ${c.h} \u00d7 ${c.d}`,
    c.hw, c.art ? "yes" : "\u2014",
    co ? String(co.yd) : "\u2014", co ? `$${co.usd}` : "\u2014"];
  let x = 0.7;
  row.forEach((v, j) => {
    s.addText(v, { x, y, w: widths[j], h: 0.42, fontFace: B, fontSize: 12.5,
      bold: j === 0, color: j === 5 ? COGNAC : INK, margin: 0, valign: "middle" });
    x += widths[j];
  });
});
s.addText("Same 54\u2033 draft canvas for comparability — leather and print quotes come next. Bigger bags cost more because the machine measured them, not because we guessed.",
  { x: 0.7, y: 6.95, w: 12.0, h: 0.4, fontFace: B, fontSize: 11.5, italic: true,
    color: MUTED, margin: 0 });

// ----------------------------------------------------------------- close
s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("Ten concepts. One afternoon.", { x: 0.9, y: 1.9, w: 11.5, h: 0.9,
  fontFace: H, fontSize: 44, bold: true, color: CREAM, margin: 0 });
s.addText("Erika picks three.", { x: 0.9, y: 2.85, w: 11.5, h: 0.9, fontFace: H,
  fontSize: 44, bold: true, color: TAN, margin: 0 });
s.addText([
  { text: "Swap the placeholder prints for real Color Me Art files", options: { bullet: true, breakLine: true } },
  { text: "Felt fit-check the three picks from their DXFs", options: { bullet: true, breakLine: true } },
  { text: "Name the first drop and shoot the renders as launch teasers", options: { bullet: true } },
], { x: 0.95, y: 4.25, w: 10.5, h: 1.7, fontFace: B, fontSize: 17, color: SOFT,
  paraSpaceAfter: 12, margin: 0 });
s.addText("3D-Fabric \u00b7 Detroit-made \u00b7 every bag a 1-of-1 \u00b7 all artifacts DRAFT",
  { x: 0.95, y: 6.75, w: 11.0, h: 0.35, fontFace: B, fontSize: 11, color: MUTED, margin: 0 });

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
