/* Friday Motion runtime. Everything is drawn on one canvas as a pure function of time,
   so the Python driver can ask for any frame: window.renderAt(seconds). */
"use strict";

const TAU = Math.PI * 2;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const eOut = (t) => 1 - Math.pow(1 - clamp(t), 3);
const eInOut = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const eBack = (t) => { t = clamp(t); const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
const eElastic = (t) => { t = clamp(t); return t === 0 || t === 1 ? t : Math.pow(2, -9 * t) * Math.sin((t * 10 - 0.75) * (TAU / 3)) + 1; };
const rng = (seed) => () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
const seg = (t, a, b) => clamp((t - a) / (b - a));

const THEMES = [
  { bg: "#f4ecd8", fg: "#17140f", accent: "#ff4d2e", alt: "#2d5bff", soft: "#e4d8bb", dark: false },
  { bg: "#0b1020", fg: "#f5f7ff", accent: "#4de1ff", alt: "#ff5fa2", soft: "#18213f", dark: true },
  { bg: "#ffd23f", fg: "#14121a", accent: "#ff3d6e", alt: "#2b2bff", soft: "#ffc400", dark: false },
  { bg: "#1b4dff", fg: "#ffffff", accent: "#ffe14d", alt: "#ff6b9a", soft: "#3b66ff", dark: true },
  { bg: "#111111", fg: "#f6f1e7", accent: "#ff7a1a", alt: "#46d6a8", soft: "#222222", dark: true },
  { bg: "#e9f3ff", fg: "#0c1b33", accent: "#1f6bff", alt: "#ff7a45", soft: "#d3e6ff", dark: false },
  { bg: "#14352b", fg: "#f2f7e8", accent: "#b6ff5c", alt: "#ffcf5c", soft: "#1f4a3c", dark: true },
  { bg: "#ff5a3d", fg: "#fff6ea", accent: "#17140f", alt: "#ffe14d", soft: "#ff7457", dark: true },
];

let W = 540, H = 960, U = 1, ZONE = 0.66, ctx = null, cvs = null, story = null;
const FONT = {
  black: '"FBlack", "Arial Black", sans-serif',
  bold: '"FBold", Arial, sans-serif',
  med: '"FMed", Arial, sans-serif',
  serif: '"FSerif", Georgia, serif',
};

/* ---------- drawing helpers ---------- */
function fit(text, family, weight, maxW, maxSize) {
  ctx.font = `${weight} 100px ${family}`;
  const w = ctx.measureText(text).width || 1;
  return Math.min(maxSize, (100 * maxW) / w);
}
const MIN_TEXT_UNITS = 64; // smallest text allowed anywhere, in design units (the short side of the frame is 1080)
let registry = null; // while a scene is being checked: every text and icon drawn is recorded here
const _col = document.createElement("canvas").getContext("2d");
function rgbOf(c) { _col.fillStyle = "#000"; _col.fillStyle = c; const v = _col.fillStyle; if (v[0] === "#") { const n = parseInt(v.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; } const m = v.match(/[\d.]+/g) || [0, 0, 0]; return [+m[0], +m[1], +m[2]]; }
function lum([r, g, b]) { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); }
function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
function backdrop(x0, y0, x1, y1) {
  let r = 0, g = 0, b = 0, n = 0;
  for (let i = 0; i < 5; i++) for (let j = 0; j < 2; j++) {
    const px = Math.round(clamp(x0 + ((x1 - x0) * (i + 0.5)) / 5, 0, W - 1)), py = Math.round(clamp(y0 + ((y1 - y0) * (j + 0.5)) / 2, 0, H - 1));
    const d = ctx.getImageData(px, py, 1, 1).data; if (d[3] < 40) continue; r += d[0]; g += d[1]; b += d[2]; n++;
  }
  return n ? [r / n, g / n, b / n] : null;
}
function text(str, x, y, size, family, color, opts = {}) {
  ctx.save();
  const m0 = ctx.getTransform(), sc = Math.hypot(m0.a, m0.b) || 1, minPx = MIN_TEXT_UNITS * U, raw = size * sc;
  if (raw < minPx) size = minPx / sc;
  ctx.font = `${opts.weight || 400} ${size}px ${family}`;
  ctx.textAlign = opts.align || "center";
  ctx.textBaseline = "middle";
  const ts = opts.scale == null ? 1 : opts.scale, tw = ctx.measureText(str).width * ts * sc, th2 = size * ts * sc;
  const dx = m0.a * x + m0.c * y + m0.e, dy = m0.b * x + m0.d * y + m0.f, al = opts.align || "center";
  const bx0 = al === "left" ? dx : al === "right" ? dx - tw : dx - tw / 2, by0 = dy - th2 * 0.5;
  const alpha = (opts.alpha == null ? 1 : opts.alpha) * ctx.globalAlpha;
  if (registry) registry.push({ kind: "text", str, x0: bx0, y0: by0, x1: bx0 + tw, y1: by0 + th2, raw, alpha });
  // keep text readable: if it would sit on a background of similar brightness, switch to black or white
  if (alpha > 0.5 && !opts.keepColor) {
    try {
      const bgc = backdrop(bx0, by0, bx0 + tw, by0 + th2);
      if (bgc && contrast(rgbOf(color), bgc) < 3.6) color = contrast([255, 255, 255], bgc) >= contrast([17, 17, 17], bgc) ? "#ffffff" : "#111111";
    } catch (e) { /* reading pixels is a nicety, never a requirement */ }
  }
  if (opts.rot || opts.scale != null) { ctx.translate(x, y); ctx.rotate(opts.rot || 0); ctx.scale(ts, ts); x = 0; y = 0; }
  if (opts.shadow) { ctx.fillStyle = opts.shadow; ctx.fillText(str, x + opts.sd * U, y + opts.sd * U); }
  ctx.globalAlpha *= opts.alpha == null ? 1 : opts.alpha;
  ctx.fillStyle = color;
  ctx.fillText(str, x, y);
  ctx.restore();
}
function rrect(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function glow(x, y, r, color, a = 1) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, color); g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.save(); ctx.globalAlpha *= a; ctx.globalCompositeOperation = "lighter"; ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill(); ctx.restore();
}
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}
function contentH() { return H * ZONE; }
function bg(th) { ctx.fillStyle = th.bg; ctx.fillRect(0, 0, W, H); }

/* ---------- backgrounds ---------- */
function dotGrid(t, th, alpha = 0.18) {
  const gap = 54 * U, r = 2.4 * U, off = (t * 14 * U) % gap;
  ctx.save(); ctx.fillStyle = hexA(th.fg, alpha);
  for (let y = -gap + off; y < H + gap; y += gap) for (let x = -gap + off; x < W + gap; x += gap) { ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill(); }
  ctx.restore();
}
function sunburst(t, th, cx, cy, rays = 18, a = 1) {
  const R = Math.hypot(W, H);
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(t * 0.12); ctx.globalAlpha = a;
  for (let i = 0; i < rays; i += 2) {
    ctx.beginPath(); ctx.moveTo(0, 0);
    ctx.arc(0, 0, R, (i / rays) * TAU, ((i + 1) / rays) * TAU); ctx.closePath();
    ctx.fillStyle = th.soft; ctx.fill();
  }
  ctx.restore();
}
function floatBlobs(t, th) {
  const r = rng(7);
  for (let i = 0; i < 5; i++) {
    const bx = r() * W, by = r() * H, sp = 0.3 + r() * 0.5, rad = (200 + r() * 260) * U;
    glow(bx + Math.sin(t * sp + i) * 60 * U, by + Math.cos(t * sp * 0.8 + i) * 60 * U, rad, hexA(i % 2 ? th.accent : th.alt, 0.5), th.dark ? 0.55 : 0.35);
  }
}

/* ---------- scenes ---------- */
function sceneKinetic(t, d, data, th) {
  bg(th); dotGrid(t, th);
  const lines = (data.lines && data.lines.length ? data.lines : [data.text || ""]).slice(0, 4);
  const hi = data.accent == null ? lines.length - 1 : clamp(data.accent, 0, lines.length - 1);
  const zone = contentH(), maxW = W * 0.86;
  const sizes = lines.map((l, i) => fit(l.toUpperCase(), FONT.black, 400, maxW, (lines.length > 2 ? 190 : 250) * U));
  const common = Math.min(...sizes), gap = common * 0.12;
  const total = lines.length * common + (lines.length - 1) * gap;
  let y = zone / 2 - total / 2 + common / 2;
  lines.forEach((line, i) => {
    const p = seg(t, 0.12 + i * 0.2, 0.12 + i * 0.2 + 0.55);
    const s = lerp(0.55, 1, eBack(p)) * (1 + 0.025 * (t / d));
    const ty = y + (1 - eOut(p)) * 90 * U;
    const isHi = i === hi;
    if (isHi && p > 0) {
      const sz = fit(line.toUpperCase(), FONT.black, 400, maxW, common);
      ctx.font = `400 ${sz}px ${FONT.black}`;
      const tw = ctx.measureText(line.toUpperCase()).width + sz * 0.5;
      ctx.save(); ctx.translate(W / 2, ty); ctx.rotate(-0.025); ctx.scale(s, s); ctx.globalAlpha = clamp(p * 3);
      ctx.fillStyle = th.accent; rrect(-tw / 2, -sz * 0.62, tw, sz * 1.24, sz * 0.2); ctx.fill(); ctx.restore();
    }
    text(line.toUpperCase(), W / 2, ty, common, FONT.black, isHi ? (th.dark && th.accent === "#17140f" ? th.fg : th.bg) : th.fg,
      { weight: 400, scale: s, alpha: clamp(p * 3), rot: isHi ? -0.025 : 0 });
    y += common + gap;
  });
  if (data.sub) text(data.sub, W / 2, zone * 0.92, 64 * U, FONT.serif, th.fg, { weight: 400, alpha: eOut(seg(t, 0.8, 1.3)) * 0.85 });
}

function sceneBurst(t, d, data, th) {
  bg(th); sunburst(t, th, W / 2, contentH() / 2, 20);
  const r = rng(11);
  for (let i = 0; i < 26; i++) {
    const ang = r() * TAU, dist = (0.3 + r() * 0.55) * W, sp = 0.3 + r() * 0.6;
    const k = (t * sp + r()) % 1, rad = (6 + r() * 14) * U * (1 - k);
    ctx.fillStyle = i % 2 ? th.accent : th.alt; ctx.beginPath();
    ctx.arc(W / 2 + Math.cos(ang) * dist * (0.25 + k), contentH() / 2 + Math.sin(ang) * dist * (0.25 + k) * 0.8, rad, 0, TAU); ctx.fill();
  }
  const words = (data.text || "").toUpperCase().split(/\s+/).filter(Boolean).slice(0, 3);
  const size = Math.min(...words.map((w) => fit(w, FONT.black, 400, W * 0.84, 280 * U)));
  const total = words.length * size * 1.0;
  words.forEach((w, i) => {
    const p = seg(t, 0.08 + i * 0.16, 0.7 + i * 0.16);
    const y = contentH() / 2 - total / 2 + size * (i + 0.5);
    text(w, W / 2, y, size, FONT.black, i === words.length - 1 ? th.accent : th.fg,
      { weight: 400, scale: lerp(0.2, 1, eElastic(p)), rot: lerp(-0.12, -0.04, eOut(p)), shadow: th.fg === "#ffffff" ? hexA("#000000", 0.35) : hexA(th.alt, 0.9), sd: size * 0.045, alpha: clamp(p * 4) });
  });
  if (data.sub) text(data.sub, W / 2, contentH() * 0.9, 64 * U, FONT.serif, th.fg, { alpha: eOut(seg(t, 0.9, 1.4)) });
}

function formatNum(v, decimals) { return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }); }
function sceneNumber(t, d, data, th) {
  bg(th); dotGrid(t, th, 0.1);
  const cx = W / 2, cy = contentH() * 0.5, R = Math.min(W * 0.36, contentH() * 0.3);
  const p = eInOut(seg(t, 0.15, 1.7));
  const val = Number(data.value) || 0, dec = String(data.value).includes(".") ? 1 : 0;
  ctx.save(); ctx.lineWidth = 26 * U; ctx.lineCap = "round";
  ctx.strokeStyle = th.soft; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.stroke();
  ctx.strokeStyle = th.accent; ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + TAU * clamp(data.fill == null ? 0.78 : data.fill) * p); ctx.stroke();
  ctx.restore();
  const label = `${data.prefix || ""}${formatNum(val * p, dec)}${data.suffix || ""}`;
  const s = fit(label, FONT.black, 400, R * 1.7, 200 * U);
  text(label, cx, cy, s, FONT.black, th.fg, { weight: 400, scale: lerp(0.85, 1, eBack(seg(t, 0, 0.5))) });
  if (data.label) {
    const ls = fit(data.label.toUpperCase(), FONT.bold, 700, W * 0.86, 74 * U);
    text(data.label.toUpperCase(), cx, cy + R + 90 * U, ls, FONT.bold, th.fg, { weight: 700, alpha: eOut(seg(t, 0.6, 1.1)) });
  }
  const r = rng(5);
  for (let i = 0; i < 14; i++) {
    const a = r() * TAU, k = eOut(seg(t, 1.6, 2.4)), rr = R + (40 + r() * 90) * U * k;
    ctx.fillStyle = i % 2 ? th.accent : th.alt; ctx.globalAlpha = (1 - k) * 0.9 * (k > 0 ? 1 : 0);
    ctx.beginPath(); ctx.arc(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 7 * U, 0, TAU); ctx.fill(); ctx.globalAlpha = 1;
  }
}

function sceneList(t, d, data, th) {
  bg(th); floatBlobs(t, th);
  const items = (data.items || []).slice(0, 5), zone = contentH();
  const ts = fit((data.title || "").toUpperCase(), FONT.black, 400, W * 0.86, 140 * U);
  text((data.title || "").toUpperCase(), W / 2, zone * 0.13, ts, FONT.black, th.fg, { weight: 400, scale: lerp(0.7, 1, eBack(seg(t, 0, 0.6))), alpha: clamp(t * 4) });
  const step = (zone * 0.72) / Math.max(items.length, 1), top = zone * 0.28;
  items.forEach((it, i) => {
    const p = seg(t, 0.4 + i * 0.3, 1.0 + i * 0.3), x = lerp(-W * 0.4, 0, eOut(p)), y = top + i * step, r = Math.min(step * 0.3, 56 * U);
    ctx.save(); ctx.globalAlpha = clamp(p * 2.5); ctx.translate(x, 0);
    ctx.fillStyle = i % 2 ? th.alt : th.accent; ctx.beginPath(); ctx.arc(W * 0.1 + r, y, r, 0, TAU); ctx.fill();
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = r * 0.22; ctx.lineCap = "round"; ctx.lineJoin = "round";
    const ck = eOut(seg(t, 0.6 + i * 0.3, 1.0 + i * 0.3)), c0 = W * 0.1 + r;
    ctx.beginPath(); ctx.moveTo(c0 - r * 0.4, y); ctx.lineTo(c0 - r * 0.1, y + r * 0.35); ctx.lineTo(c0 - r * 0.4 + r * 0.9 * ck, y + r * 0.35 - r * 0.7 * ck); ctx.stroke();
    text(it, W * 0.1 + r * 2.5, y, fit(it, FONT.bold, 700, W * 0.78 - r * 2, 96 * U), FONT.bold, th.fg, { weight: 700, align: "left" });
    ctx.restore();
  });
}

function truchet(t, th) {
  const n = W > H ? 10 : 6, cell = W / n, rows = Math.ceil(contentH() / cell) + 1, r = rng(23);
  ctx.save(); ctx.lineWidth = cell * 0.2; ctx.lineCap = "butt";
  for (let j = 0; j < rows; j++) for (let i = 0; i < n; i++) {
    const flip = r() < 0.5, wob = Math.sin(t * 1.4 + i * 0.7 + j * 0.9) * 0.5 + 0.5;
    const x = i * cell, y = j * cell; ctx.strokeStyle = (i + j) % 2 ? th.accent : th.alt;
    ctx.save(); ctx.translate(x + cell / 2, y + cell / 2); ctx.rotate((flip ? Math.PI / 2 : 0) + (wob > 0.5 ? Math.PI / 2 * eInOut((wob - 0.5) * 2) * 0 : 0));
    ctx.translate(-cell / 2, -cell / 2);
    ctx.beginPath(); ctx.arc(0, 0, cell / 2, 0, Math.PI / 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(cell, cell, cell / 2, Math.PI, Math.PI * 1.5); ctx.stroke(); ctx.restore();
  }
  ctx.restore();
}
function scenePattern(t, d, data, th) {
  bg(th); ctx.save(); ctx.translate(0, Math.sin(t * 0.8) * 8 * U); truchet(t, th); ctx.restore();
  const cw = W * 0.82, ch = contentH() * 0.3, cx = W / 2, cy = contentH() / 2;
  const p = eBack(seg(t, 0.1, 0.7));
  ctx.save(); ctx.translate(cx, cy); ctx.scale(p, p); ctx.rotate(lerp(0.08, -0.02, eOut(seg(t, 0.1, 0.8))));
  ctx.fillStyle = th.bg; ctx.shadowColor = "rgba(0,0,0,0.35)"; ctx.shadowBlur = 40 * U; ctx.shadowOffsetY = 14 * U;
  rrect(-cw / 2, -ch / 2, cw, ch, 36 * U); ctx.fill(); ctx.shadowColor = "transparent";
  const s = fit((data.text || "").toUpperCase(), FONT.black, 400, cw * 0.86, 150 * U);
  text((data.text || "").toUpperCase(), 0, data.sub ? -ch * 0.1 : 0, s, FONT.black, th.fg, { weight: 400 });
  if (data.sub) text(data.sub, 0, ch * 0.28, fit(data.sub, FONT.serif, 400, cw * 0.86, 64 * U), FONT.serif, th.accent, { weight: 400 });
  ctx.restore();
}

function project(x, y, z, cam) {
  const cy = Math.cos(cam.ry), sy = Math.sin(cam.ry), cx = Math.cos(cam.rx), sx = Math.sin(cam.rx);
  let X = x * cy - z * sy, Z = x * sy + z * cy, Y = y * cx - Z * sx; Z = y * sx + Z * cx;
  const f = cam.f / (cam.f + Z + cam.dz);
  return [cam.cx + X * f, cam.cy + Y * f, f, Z];
}
function sceneRing(t, d, data, th) {
  ctx.fillStyle = "#05070f"; ctx.fillRect(0, 0, W, H);
  const cam = { rx: 1.0 + Math.sin(t * 0.5) * 0.18, ry: t * 0.35, f: 700 * U, dz: 280 * U, cx: W / 2, cy: contentH() * 0.45 };
  const r = rng(99), N = 900, R = Math.min(W, H) * 0.52, grow = eOut(seg(t, 0, 1.2));
  ctx.save(); ctx.globalCompositeOperation = "lighter";
  for (let i = 0; i < N; i++) {
    const a = r() * TAU, off = (r() - 0.5) * 0.55, lift = (r() - 0.5) * 0.35, ph = r() * TAU;
    const rr = R * grow * (1 + off * (0.4 + 0.2 * Math.sin(t * 1.5 + ph)));
    const [x, y, f] = project(Math.cos(a + t * 0.25) * rr, lift * R * grow + Math.sin(a * 3 + t * 2) * 12 * U, Math.sin(a + t * 0.25) * rr, cam);
    const col = i % 3 === 0 ? th.alt : th.accent;
    ctx.fillStyle = hexA(col, clamp(0.25 + f * 0.5)); ctx.beginPath(); ctx.arc(x, y, Math.max(1, 5.5 * U * f), 0, TAU); ctx.fill();
  }
  ctx.restore();
  glow(W / 2, contentH() * 0.45, R * 1.2, hexA(th.accent, 0.25), 0.7);
  const s = fit((data.text || "").toUpperCase(), FONT.black, 400, W * 0.84, 150 * U);
  text((data.text || "").toUpperCase(), W / 2, contentH() * 0.45, s, FONT.black, "#ffffff", { weight: 400, scale: lerp(0.85, 1, eBack(seg(t, 0.3, 1))), alpha: eOut(seg(t, 0.2, 0.7)) });
  if (data.sub) text(data.sub, W / 2, contentH() * 0.45 + s * 0.8, 64 * U, FONT.serif, "#cfe8ff", { alpha: eOut(seg(t, 0.9, 1.4)) });
}

function sceneCube(t, d, data, th) {
  bg(th); floatBlobs(t, th);
  const cam = { rx: -0.5, ry: 0, f: 800 * U, dz: 260 * U, cx: W / 2, cy: contentH() * 0.46 };
  const size = Math.min(W, contentH()) * 0.27 * lerp(0.2, 1, eBack(seg(t, 0, 0.8)));
  const rot = t * 0.9, rot2 = t * 0.6, V = [];
  for (let i = 0; i < 8; i++) {
    let x = (i & 1 ? 1 : -1) * size, y = (i & 2 ? 1 : -1) * size, z = (i & 4 ? 1 : -1) * size;
    const x1 = x * Math.cos(rot) - z * Math.sin(rot), z1 = x * Math.sin(rot) + z * Math.cos(rot);
    const y1 = y * Math.cos(rot2) - z1 * Math.sin(rot2), z2 = y * Math.sin(rot2) + z1 * Math.cos(rot2);
    V.push(project(x1, y1, z2, cam));
  }
  const faces = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]];
  const order = faces.map((f, i) => ({ f, z: f.reduce((s, k) => s + V[k][3], 0) / 4, i })).sort((a, b) => b.z - a.z);
  order.forEach(({ f, i }) => {
    ctx.beginPath(); f.forEach((k, n) => (n ? ctx.lineTo(V[k][0], V[k][1]) : ctx.moveTo(V[k][0], V[k][1]))); ctx.closePath();
    ctx.fillStyle = hexA(i % 2 ? th.accent : th.alt, 0.28 + 0.1 * (i % 3)); ctx.fill();
    ctx.strokeStyle = th.fg; ctx.lineWidth = 4 * U; ctx.lineJoin = "round"; ctx.stroke();
  });
  glow(W / 2, contentH() * 0.46, size * 2.6, hexA(th.accent, 0.35), th.dark ? 0.8 : 0.4);
  const s = fit((data.text || "").toUpperCase(), FONT.black, 400, W * 0.84, 130 * U), ty = contentH() * 0.46 + size * 2.3;
  text((data.text || "").toUpperCase(), W / 2, Math.min(ty, contentH() * 0.9), s, FONT.black, th.fg, { weight: 400, alpha: eOut(seg(t, 0.4, 0.9)), scale: lerp(0.8, 1, eBack(seg(t, 0.4, 1))) });
}

function scenePhone(t, d, data, th) {
  bg(th); floatBlobs(t, th);
  const zone = contentH(), pw = Math.min(W * 0.72, zone * 0.5), ph = pw * 1.95, cx = W / 2;
  const enter = eBack(seg(t, 0, 0.8)), cy = zone * 0.56 + (1 - enter) * 300 * U + Math.sin(t * 1.6) * 8 * U;
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.08 + Math.sin(t * 0.9) * 0.015); ctx.scale(Math.min(1, zone * 0.78 / ph) * enter, Math.min(1, zone * 0.78 / ph) * enter);
  ctx.fillStyle = "#0e0e12"; ctx.shadowColor = "rgba(0,0,0,0.45)"; ctx.shadowBlur = 50 * U; ctx.shadowOffsetY = 24 * U;
  rrect(-pw / 2, -ph / 2, pw, ph, pw * 0.14); ctx.fill(); ctx.shadowColor = "transparent";
  const m = pw * 0.035; ctx.save(); rrect(-pw / 2 + m, -ph / 2 + m, pw - 2 * m, ph - 2 * m, pw * 0.11); ctx.clip();
  ctx.fillStyle = th.dark ? "#161a2e" : "#ffffff"; ctx.fillRect(-pw / 2, -ph / 2, pw, ph);
  const hdr = ph * 0.14; ctx.fillStyle = th.accent; ctx.fillRect(-pw / 2, -ph / 2, pw, hdr);
  const items = (data.items || []).slice(0, 4), cardH = ph * 0.15;
  items.forEach((it, i) => {
    const p = eOut(seg(t, 0.5 + i * 0.3, 1.0 + i * 0.3)), y = -ph / 2 + hdr + ph * 0.04 + i * (cardH + ph * 0.025);
    ctx.save(); ctx.globalAlpha = p; ctx.translate(lerp(pw * 0.4, 0, p), 0);
    ctx.fillStyle = th.dark ? th.soft : "#f1f3f8"; rrect(-pw * 0.43, y, pw * 0.86, cardH, cardH * 0.22); ctx.fill();
    ctx.fillStyle = i % 2 ? th.alt : th.accent; ctx.beginPath(); ctx.arc(-pw * 0.43 + cardH * 0.5, y + cardH / 2, cardH * 0.26, 0, TAU); ctx.fill();
    ctx.fillStyle = hexA(th.fg, 0.35); rrect(-pw * 0.43 + cardH * 0.95, y + cardH * 0.3, pw * 0.5, cardH * 0.16, cardH * 0.08); ctx.fill();
    ctx.fillStyle = hexA(th.fg, 0.2); rrect(-pw * 0.43 + cardH * 0.95, y + cardH * 0.56, pw * 0.34, cardH * 0.14, cardH * 0.07); ctx.fill();
    ctx.restore();
  });
  ctx.restore();
  ctx.fillStyle = "#0e0e12"; rrect(-pw * 0.17, -ph / 2 + m * 1.6, pw * 0.34, m * 1.6, m * 0.8); ctx.fill();
  ctx.restore();
  if (data.text) {
    const s = fit(data.text.toUpperCase(), FONT.black, 400, W * 0.86, 120 * U);
    text(data.text.toUpperCase(), W / 2, zone * 0.07, s, FONT.black, th.fg, { weight: 400, alpha: eOut(seg(t, 0.2, 0.7)) });
  }
}

function sceneRoute(t, d, data, th) {
  ctx.fillStyle = "#0a1224"; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(120,160,255,0.12)"; ctx.lineWidth = 2 * U;
  const g = 100 * U, off = (t * 10 * U) % g;
  for (let x = -g + off; x < W + g; x += g) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = -g + off; y < H + g; y += g) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  const names = (data.points || []).slice(0, 4), n = Math.max(2, names.length), zone = contentH();
  const pts = Array.from({ length: n }, (_, i) => [W * (i % 2 ? 0.7 : 0.28), zone * (0.18 + (0.66 * i) / (n - 1))]);
  const prog = eInOut(seg(t, 0.3, 0.3 + 1.0 * (n - 1) * 0.9 + 0.4)) * (n - 1);
  ctx.save(); ctx.lineWidth = 14 * U; ctx.lineCap = "round"; ctx.setLineDash([22 * U, 16 * U]); ctx.lineDashOffset = -t * 40 * U;
  ctx.strokeStyle = th.accent; ctx.shadowColor = th.accent; ctx.shadowBlur = 18 * U;
  for (let i = 0; i < n - 1; i++) {
    const k = clamp(prog - i); if (k <= 0) continue;
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], mx = (x0 + x1) / 2, my = (y0 + y1) / 2 + (i % 2 ? -1 : 1) * 40 * U;
    const q = (u) => [(1 - u) * (1 - u) * x0 + 2 * (1 - u) * u * mx + u * u * x1, (1 - u) * (1 - u) * y0 + 2 * (1 - u) * u * my + u * u * y1];
    ctx.beginPath(); for (let s = 0; s <= 24; s++) { const [x, y] = q((s / 24) * k); s ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke();
  }
  ctx.restore();
  pts.forEach(([x, y], i) => {
    const p = eElastic(seg(prog, i - 0.15, i + 0.1)), pr = 40 * U * p;
    glow(x, y, 90 * U * p, hexA(th.accent, 0.5), 0.8);
    ctx.fillStyle = i === n - 1 ? th.alt : th.accent; ctx.beginPath(); ctx.arc(x, y - 10 * U * (1 - p), pr, 0, TAU); ctx.fill();
    ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(x, y - 10 * U * (1 - p), pr * 0.4, 0, TAU); ctx.fill();
    if (names[i]) text(names[i], x + (x < W / 2 ? 1 : -1) * 62 * U, y, fit(names[i], FONT.bold, 700, W * 0.42, 80 * U), FONT.bold, "#ffffff", { weight: 700, align: x < W / 2 ? "left" : "right", alpha: clamp(p) });
  });
  if (data.title) text(data.title.toUpperCase(), W / 2, zone * 0.06, fit(data.title.toUpperCase(), FONT.black, 400, W * 0.84, 110 * U), FONT.black, "#ffffff", { weight: 400 });
}

/* Isometric low-poly world: a small city that grows on a plinth while the camera orbits. */
function sceneWorld(t, d, data, th) {
  const sky = ctx.createLinearGradient(0, 0, 0, H); sky.addColorStop(0, th.dark ? th.bg : th.soft); sky.addColorStop(1, th.dark ? th.soft : th.bg);
  ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);
  const cam = { rx: 0.95, ry: 0.8 + t * 0.32, f: 1300 * U, dz: 450 * U, cx: W / 2, cy: contentH() * 0.45 };
  const S = Math.min(W, contentH()) * 0.066, G = 6, r = rng(data.seed || 3), pal = [th.accent, th.alt, th.fg, th.soft];
  const items = [];
  for (let gx = 0; gx < G; gx++) for (let gz = 0; gz < G; gz++) {
    const road = gx === 2 || gz === 3, hgt = road ? 0.1 : 0.5 + r() * 3.2 * (r() < 0.25 ? 1.6 : 1), c = road ? "#3a3f55" : pal[Math.floor(r() * 3)];
    const delay = (gx + gz) * 0.07 + r() * 0.2, k = eBack(seg(t, 0.15 + delay, 0.85 + delay));
    items.push({ x: gx - G / 2 + 0.5, z: gz - G / 2 + 0.5, h: hgt * k, c });
  }
  const cube = (cx, cz, h, c) => {
    const x0 = (cx - 0.42) * S * 2, x1 = (cx + 0.42) * S * 2, z0 = (cz - 0.42) * S * 2, z1 = (cz + 0.42) * S * 2, y1 = -h * S * 2;
    const P = [[x0, 0, z0], [x1, 0, z0], [x1, 0, z1], [x0, 0, z1], [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]].map((p) => project(p[0], p[1], p[2], cam));
    const fs = [[4, 5, 6, 7, 1.0], [0, 1, 5, 4, 0.78], [1, 2, 6, 5, 0.6], [2, 3, 7, 6, 0.78], [3, 0, 4, 7, 0.6]];
    fs.forEach(([a, b, c2, d2, shade]) => {
      const nz = (P[b][0] - P[a][0]) * (P[c2][1] - P[a][1]) - (P[b][1] - P[a][1]) * (P[c2][0] - P[a][0]);
      if (nz > 0 && shade < 1) return;
      ctx.beginPath(); [a, b, c2, d2].forEach((k, n) => (n ? ctx.lineTo(P[k][0], P[k][1]) : ctx.moveTo(P[k][0], P[k][1]))); ctx.closePath();
      ctx.fillStyle = shadeColor(c, shade); ctx.fill();
    });
    return P[0][3];
  };
  const pw = G / 2 + 0.3;
  cube(0, 0, -0.3, "#222638");
  const base = [[-pw, -pw], [pw, -pw], [pw, pw], [-pw, pw]].map(([x, z]) => project(x * S * 2, 0, z * S * 2, cam));
  ctx.beginPath(); base.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.closePath(); ctx.fillStyle = th.dark ? "#1d2440" : "#cfd8ee"; ctx.fill();
  items.map((it) => ({ it, z: project(it.x * S * 2, 0, it.z * S * 2, cam)[3] })).sort((a, b) => b.z - a.z).forEach(({ it }) => cube(it.x, it.z, it.h, it.c));
  if (data.text) {
    const s = fit(data.text.toUpperCase(), FONT.black, 400, W * 0.84, 110 * U);
    text(data.text.toUpperCase(), W / 2, contentH() * 0.94, s, FONT.black, th.fg, { weight: 400, alpha: eOut(seg(t, 0.3, 0.8)) });
  }
}
function shadeColor(hex, k) {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${Math.round((n >> 16) * k)},${Math.round(((n >> 8) & 255) * k)},${Math.round((n & 255) * k)})`;
}

const SCENES = { kinetic: sceneKinetic, burst: sceneBurst, number: sceneNumber, list: sceneList, pattern: scenePattern, ring: sceneRing, cube: sceneCube, phone: scenePhone, route: sceneRoute, world: sceneWorld };

/* ---------- timeline and transitions ---------- */
function themeFor(b) { return THEMES[((b.theme || 0) % THEMES.length + THEMES.length) % THEMES.length]; }
let strict = false;
function drawBeat(b, local) {
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  let done = false;
  if (!strict) bg(themeFor(b)); // every scene starts from a solid colour, so nothing of the previous scene can show through
  if (b.fn && !b.bad) {
    const th = themeFor(b);
    ctx.save(); ctx.scale(U, U);
    try { b.fn(makeApi(th), Math.max(0, local), b.dur); done = true; }
    catch (e) { b.err = String(e); b.bad = true; if (strict) { ctx.restore(); ctx.restore(); throw e; } }
    ctx.restore();
  }
  if (!done) {
    const fn = SCENES[b.type] || sceneKinetic;
    try { TH = themeFor(b); fn(Math.max(0, local), b.dur, b.data || {}, themeFor(b)); } catch (e) { bg(themeFor(b)); }
  }
  ctx.restore();
}
const WIPE = 0.32;
function wipeClip(kind, p) {
  const e = p > 0.985 ? 1 : eInOut(p), o = 2; // o: overshoot in pixels so rounding never leaves a hairline
  ctx.beginPath();
  if (kind === "circle") ctx.arc(W / 2, H * 0.45, Math.hypot(W, H) * e + o, 0, TAU);
  else if (kind === "up") ctx.rect(-o, H * (1 - e) - o, W + 2 * o, H * e + 2 * o);
  else if (kind === "side") ctx.rect(-o, -o, W * e + 2 * o, H + 2 * o);
  else { const n = 5, bh = Math.ceil(H / n); for (let i = 0; i < n; i++) ctx.rect(-o, i * bh - 1, (W + 2 * o) * clamp(e * 1.4 - i * 0.08), bh + 2); }
  ctx.clip();
}
window.setup = function (s, width, height) {
  story = s; W = width; H = height; U = Math.min(W, H) / 1080; ZONE = 0.92;
  cvs = document.getElementById("c"); cvs.width = W; cvs.height = H; ctx = cvs.getContext("2d");
  let at = 0; story.beats.forEach((b) => { b.start = at; at += b.dur; b.fn = b.code ? window.compileScene(b.code) : null; if (b.code && !b.fn) b.bad = true; });
};
window.renderAt = function (t) {
  const beats = story.beats; let i = beats.findIndex((b) => t < b.start + b.dur); if (i < 0) i = beats.length - 1;
  const b = beats[i], local = t - b.start, kinds = ["circle", "up", "side"];
  if (i > 0 && local < WIPE) {
    const prev = beats[i - 1]; drawBeat(prev, prev.dur + local);
    ctx.save(); wipeClip(kinds[i % kinds.length], local / WIPE); drawBeat(b, local); ctx.restore();
  } else drawBeat(b, local);
};
window.loadFonts = async function (base) {
  const defs = [["FBlack", "InterDisplay-Black.otf"], ["FBold", "Inter-Bold.otf"], ["FMed", "Inter-Medium.otf"], ["FSerif", "Lora-Italic-Variable.ttf"]];
  for (const [name, file] of defs) { const f = new FontFace(name, `url(${base}/${file})`); await f.load(); document.fonts.add(f); }
  return true;
};

/* Dry-run every AI-written scene. It must run without errors, fill the frame, show a real picture, keep moving,
   use readable text that stays inside the frame, and not pile things on top of each other. */
window.checkBeats = function () {
  const PW = 108, PH = Math.round((PW * H) / W), probe = document.createElement("canvas"); probe.width = PW; probe.height = PH;
  const pc = probe.getContext("2d", { willReadFrequently: true }), out = []; strict = true;
  const grab = () => { pc.clearRect(0, 0, PW, PH); pc.drawImage(cvs, 0, 0, PW, PH); return pc.getImageData(0, 0, PW, PH).data; };
  const L = (d, k) => d[k * 4] * 0.3 + d[k * 4 + 1] * 0.6 + d[k * 4 + 2] * 0.1;
  story.beats.forEach((b) => {
    if (!b.code) { out.push(null); return; }
    if (!b.fn) { out.push({ ok: false, err: "rejected by the safety filter" }); return; }
    const problems = [];
    try {
      const times = []; for (let x = 0.4; x < b.dur * 0.97; x += 0.8) times.push(x); times.push(b.dur * 0.97);
      const shots = [], regs = [], t0 = performance.now();
      times.forEach((tt) => { ctx.clearRect(0, 0, W, H); registry = []; drawBeat(b, tt); regs.push(registry); registry = null; shots.push(grab()); });
      const ms = (performance.now() - t0) / times.length, n = PW * PH, last = shots[shots.length - 1], mid = shots[Math.floor(shots.length * 0.6)];
      let holes = 0; for (let k = 0; k < n; k++) if (last[k * 4 + 3] < 250) holes++;
      if (holes / n > 0.005) problems.push("the background does not fill the frame: call g.bg() first");
      const detail = (d) => { let all = 0, band = 0, nb = 0; for (let y = 0; y < PH - 1; y++) for (let x = 0; x < PW - 1; x++) { const k = y * PW + x, e = Math.abs(d[k * 4] - d[(k + 1) * 4]) + Math.abs(d[k * 4 + 1] - d[(k + 1) * 4 + 1]) + Math.abs(d[k * 4 + 2] - d[(k + 1) * 4 + 2]) + Math.abs(d[k * 4] - d[(k + PW) * 4]) + Math.abs(d[k * 4 + 1] - d[(k + PW) * 4 + 1]) + Math.abs(d[k * 4 + 2] - d[(k + PW) * 4 + 2]); const hit = e > 60 ? 1 : 0; all += hit; if (y > PH * 0.22 && y < PH * 0.78) { band += hit; nb++; } } return [all / n, band / Math.max(nb, 1)]; };
      const [edgeAll, edgeMid] = detail(last), [edgeAll2] = detail(mid);
      b.metrics = { edgeAll, edgeMid, edgeAll2 };
      if (edgeAll < 0.022 || edgeAll2 < 0.015 || edgeMid < 0.012) problems.push("the frame is mostly empty: draw a large main picture of the idea in the middle");
      // movement: no stretch longer than 2.4 s where nothing changes
      let still = 0, worst = 0;
      for (let i = 1; i < shots.length; i++) { let ch = 0; for (let k = 0; k < n; k++) if (Math.abs(shots[i][k * 4] - shots[i - 1][k * 4]) + Math.abs(shots[i][k * 4 + 1] - shots[i - 1][k * 4 + 1]) + Math.abs(shots[i][k * 4 + 2] - shots[i - 1][k * 4 + 2]) > 36) ch++; still = ch / n < 0.0012 ? still + (times[i] - times[i - 1]) : 0; worst = Math.max(worst, still); }
      if (worst > 2.4) problems.push(`nothing moves for ${worst.toFixed(1)} seconds: keep something animating through the whole scene`);
      // text rules, judged on the settled frames
      const settled = regs.slice(Math.floor(regs.length * 0.5)), fin = regs[regs.length - 1], seen = new Set();
      const say = (m) => { if (!seen.has(m)) { seen.add(m); problems.push(m); } };
      const inset = Math.min(W, H) * 0.02;
      settled.forEach((r) => r.forEach((e) => {
        if (e.kind !== "text" || e.alpha < 0.6) return;
        if (e.raw < MIN_TEXT_UNITS * U * 0.97) say(`text "${e.str.slice(0, 24)}" is too small (${Math.round(e.raw / U)}); every text must be at least ${MIN_TEXT_UNITS}`);
        if (e.x0 < -inset || e.x1 > W + inset || e.y0 < -inset || e.y1 > H + inset) say(`text "${e.str.slice(0, 24)}" runs off the edge of the frame`);
      }));
      const items = fin.filter((e) => e.alpha >= 0.6);
      for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
        const a = items[i], c = items[j]; if (a.kind === "icon" && c.kind === "icon") continue;
        const w = Math.min(a.x1, c.x1) - Math.max(a.x0, c.x0), h = Math.min(a.y1, c.y1) - Math.max(a.y0, c.y0);
        if (w > 0 && h > 0) { const small = Math.min((a.x1 - a.x0) * (a.y1 - a.y0), (c.x1 - c.x0) * (c.y1 - c.y0)) || 1; if ((w * h) / small > 0.12) say(`${a.kind === "text" ? `text "${a.str.slice(0, 20)}"` : "an icon"} overlaps ${c.kind === "text" ? `text "${c.str.slice(0, 20)}"` : "an icon"}`); }
      }
      if (ms > 200) problems.push("the scene is too slow to draw");
      if (b.bad && b.err) problems.push(b.err);
      out.push({ ok: problems.length === 0, err: problems.slice(0, 3).join("; "), ms, metrics: b.metrics });
    } catch (e) { registry = null; out.push({ ok: false, err: String(e).slice(0, 160) }); }
  });
  strict = false; registry = null; return out;
};
window.disableBeat = function (i) { story.beats[i].bad = true; story.beats[i].fn = null; };
