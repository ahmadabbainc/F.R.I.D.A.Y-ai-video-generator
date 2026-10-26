/* Friday Motion toolkit: a drawn icon library and the safe API that AI-written scene code runs against.
   Scene code is the BODY of function (g, t, d): g is the toolkit, t the scene time in seconds, d its length.
   Everything is drawn in "design units": the short side of the frame is 1080 units. */
"use strict";

const IC = { k: "#1b1f2a", w: "#ffffff", y: "#ffc83d", Y: "#c98a00", g: "#2fbf71", r: "#ff4d6d", u: "#3aa0ff", n: "#8b5a2b", s: "#9aa5b1", o: "#ff7a1a", l: "#e8eef7" };
let TH = THEMES[0];
const col = (k) => (!k ? null : k === "a" ? TH.accent : k === "b" ? TH.alt : k === "f" ? TH.fg : k === "p" ? TH.bg : IC[k] || k);
function P(d, fill, stroke, sw) {
  const p = new Path2D(d);
  if (fill) { ctx.fillStyle = col(fill); ctx.fill(p); }
  if (stroke) { ctx.strokeStyle = col(stroke); ctx.lineWidth = sw || 4; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.stroke(p); }
}
function line(d, color, w, prog, len) {
  ctx.save(); ctx.strokeStyle = col(color); ctx.lineWidth = w; ctx.lineCap = "round"; ctx.lineJoin = "round";
  if (prog != null) { ctx.setLineDash([len, len]); ctx.lineDashOffset = len * (1 - clamp(prog)); }
  ctx.stroke(new Path2D(d)); ctx.restore();
}
function circ(x, y, r, fill, stroke, sw) { P(`M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z`, fill, stroke, sw); }

const ICONS = {
  rocket: { idle: "bob", draw: (t) => {
    ctx.save(); ctx.translate(50, 68); ctx.scale(1, 0.8 + 0.35 * Math.abs(Math.sin(t * 22))); ctx.translate(-50, -68);
    P("M40 66 Q50 100 60 66Z", "o"); P("M44 66 Q50 90 56 66Z", "y"); ctx.restore();
    P("M34 46 L14 72 L36 68Z M66 46 L86 72 L64 68Z", "a", "k", 3);
    P("M50 4 C70 18 74 44 66 70 L34 70 C26 44 30 18 50 4Z", "w", "k", 3.5);
    circ(50, 34, 9, "b", "k", 3.5); P("M38 70 H62 V76 H38Z", "k");
  } },
  coin: { idle: "pulse", draw: (t) => {
    circ(50, 50, 38, "y", "Y", 5); circ(50, 50, 28, null, "Y", 3);
    ctx.save(); ctx.translate(50, 54); ctx.fillStyle = IC.Y; ctx.font = `400 46px ${FONT.black}`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("$", 0, 0); ctx.restore();
    P("M24 34 Q30 22 42 18", null, "w", 3);
  } },
  bulb: { idle: "pulse", draw: (t) => {
    glow(50, 40, 60 + 8 * Math.sin(t * 4), "rgba(255,210,80,0.9)", 0.6);
    P("M50 8 C72 8 84 26 82 42 C81 54 70 60 67 72 L33 72 C30 60 19 54 18 42 C16 26 28 8 50 8Z", "y", "Y", 4);
    P("M33 78 H67 V86 H33Z M38 88 H62 V94 H38Z", "s", "k", 2.5); line("M40 44 L50 56 L60 44 M50 56 V72", "Y", 4);
  } },
  clock: { idle: "none", draw: (t) => {
    circ(50, 50, 40, "w", "k", 5);
    for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU; line(`M${50 + Math.sin(a) * 33} ${50 - Math.cos(a) * 33}L${50 + Math.sin(a) * 37} ${50 - Math.cos(a) * 37}`, "k", 3); }
    const m = t * 1.6, h = m / 12; line(`M50 50L${50 + Math.sin(m) * 30} ${50 - Math.cos(m) * 30}`, "a", 4); line(`M50 50L${50 + Math.sin(h) * 20} ${50 - Math.cos(h) * 20}`, "k", 6); circ(50, 50, 4, "k");
  } },
  heart: { idle: "beat", draw: () => P("M50 90 C18 66 8 46 8 32 C8 18 20 8 32 8 C40 8 46 12 50 20 C54 12 60 8 68 8 C80 8 92 18 92 32 C92 46 82 66 50 90Z", "r", "k", 3.5) },
  shield: { idle: "pulse", draw: (t) => {
    P("M50 6 L86 18 V48 C86 72 70 86 50 94 C30 86 14 72 14 48 V18Z", "b", "k", 4);
    line("M32 50 L45 63 L69 37", "w", 9, eOut(seg(t, 0.2, 0.8)), 90);
  } },
  lock: { idle: "bob", draw: () => {
    line("M30 46 V32 C30 18 38 10 50 10 C62 10 70 18 70 32 V46", "k", 9); P("M20 44 H80 V90 H20Z", "a", "k", 4);
    circ(50, 62, 7, "k"); P("M47 66 H53 V78 H47Z", "k");
  } },
  cart: { idle: "bob", draw: (t) => {
    P("M24 28 H90 L79 62 H33Z", "a", "k", 3); line("M6 14 H20 L34 64 H80", "k", 6);
    circ(40, 80, 8, "k"); circ(72, 80, 8, "k"); line("M40 40 V54 M56 40 V54 M72 40 V54", "w", 3);
  } },
  house: { idle: "pulse", draw: () => {
    P("M18 46 H82 V90 H18Z", "w", "k", 4); P("M6 50 L50 10 L94 50Z", "a", "k", 4);
    P("M42 62 H58 V90 H42Z", "b", "k", 3); P("M24 56 H36 V68 H24Z M64 56 H76 V68 H64Z", "u", "k", 3);
  } },
  gear: { idle: "none", draw: (t) => {
    ctx.save(); ctx.translate(50, 50); ctx.rotate(t * 0.9); ctx.fillStyle = col("s"); ctx.strokeStyle = IC.k; ctx.lineWidth = 4; ctx.lineJoin = "round";
    ctx.beginPath(); for (let i = 0; i < 8; i++) { const a = (i / 8) * TAU, w = 0.2; [[-w, 30], [-w * 0.6, 42], [w * 0.6, 42], [w, 30]].forEach(([da, r], k) => { const x = Math.cos(a + da) * r, y = Math.sin(a + da) * r; (i === 0 && k === 0) ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }); }
    ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.beginPath(); ctx.arc(0, 0, 13, 0, TAU); ctx.fillStyle = col("p"); ctx.fill(); ctx.stroke(); ctx.restore();
  } },
  globe: { idle: "none", draw: (t) => {
    const land = new Path2D("M20 30 C30 18 46 20 50 30 C56 40 44 48 38 56 C34 64 24 60 22 50Z M62 44 C74 38 90 46 88 60 C86 72 70 76 64 66Z M60 18 C68 14 78 18 76 24 C70 28 62 26 60 18Z");
    circ(50, 50, 40, "u", "k", 4); ctx.save(); ctx.beginPath(); ctx.arc(50, 50, 38, 0, TAU); ctx.clip();
    const sh = (t * 18) % 100; ctx.fillStyle = IC.g;
    for (const o of [-100, 0, 100]) { ctx.save(); ctx.translate(o + sh, 0); ctx.fill(land); ctx.restore(); }
    ctx.restore(); circ(50, 50, 40, null, "k", 4); P("M30 24 Q38 14 52 12", null, "w", 3);
  } },
  star: { idle: "spin", draw: () => P("M50 6 L62 36 L94 38 L69 58 L78 90 L50 72 L22 90 L31 58 L6 38 L38 36Z", "y", "Y", 4) },
  growth: { idle: "none", draw: (t) => {
    [[16, 42, "b"], [40, 60, "a"], [64, 78, "g"]].forEach(([x, h, c], i) => { const k = eBack(seg(t, 0.1 + i * 0.25, 0.7 + i * 0.25)); P(`M${x} 90 V${90 - h * k} H${x + 20} V90Z`, c, "k", 3); });
    line("M10 52 L36 38 L52 46 L88 12", "r", 6, eOut(seg(t, 0.8, 1.6)), 140); const k = seg(t, 1.4, 1.8); if (k > 0) P("M88 12 L72 14 L86 26Z", "r");
  } },
  magnifier: { idle: "swing", draw: () => {
    line("M62 62 L90 90", "a", 13); circ(42, 42, 28, "rgba(200,225,255,0.55)", "k", 8); P("M26 36 Q30 26 40 22", null, "w", 4);
  } },
  person: { idle: "bob", draw: () => { P("M16 94 C16 66 32 54 50 54 C68 54 84 66 84 94Z", "b", "k", 4); circ(50, 30, 18, "#f2c49b", "k", 4); P("M32 26 C34 12 66 12 68 26 C60 18 42 18 32 26Z", "k"); } },
  check: { idle: "pulse", draw: (t) => { circ(50, 50, 42, "g", "k", 4); line("M28 52 L44 68 L74 34", "w", 11, eOut(seg(t, 0.1, 0.7)), 100); } },
  phone: { idle: "bob", draw: (t) => {
    P("M30 6 H70 a8 8 0 0 1 8 8 V86 a8 8 0 0 1 -8 8 H30 a8 8 0 0 1 -8 -8 V14 a8 8 0 0 1 8 -8Z", "k"); P("M28 16 H72 V80 H28Z", "b");
    P("M34 24 H66 V34 H34Z M34 40 H66 V50 H34Z M34 56 H54 V66 H34Z", "w"); circ(50, 87, 3.5, "s");
  } },
  laptop: { idle: "pulse", draw: () => { P("M16 22 H84 V66 H16Z", "k"); P("M21 27 H79 V61 H21Z", "b"); P("M30 36 H62 M30 46 H70 M30 54 H52", null, "w", 4); P("M6 70 H94 L88 80 H12Z", "s", "k", 3); } },
  cloud: { idle: "bob", draw: () => P("M26 76 C8 76 6 50 26 48 C26 28 54 22 64 40 C84 34 96 56 82 70 C80 74 76 76 70 76Z", "l", "u", 4) },
  sun: { idle: "none", draw: (t) => {
    glow(50, 50, 55, "rgba(255,200,60,0.8)", 0.6); ctx.save(); ctx.translate(50, 50); ctx.rotate(t * 0.5);
    for (let i = 0; i < 10; i++) { ctx.rotate(TAU / 10); line("M0 -34L0 -46", "y", 6); } ctx.restore(); circ(50, 50, 26, "y", "Y", 4);
  } },
  tree: { idle: "swing", draw: () => { P("M44 62 H56 V92 H44Z", "n", "k", 3); P("M50 6 L80 40 H64 L88 70 H12 L36 40 H20Z", "g", "k", 4); } },
  car: { idle: "bob", draw: (t) => {
    P("M6 64 L12 46 C14 42 18 40 22 40 H34 L44 24 H66 L78 40 C86 42 92 48 94 56 V66 H6Z", "a", "k", 4); P("M40 40 L48 29 H62 L70 40Z", "u", "k", 2.5);
    [28, 74].forEach((x) => { ctx.save(); ctx.translate(x, 68); ctx.rotate(t * 8); circ(0, 0, 12, "k"); circ(0, 0, 5, "s"); line("M-5 0H5", "w", 2); ctx.restore(); });
  } },
  plane: { idle: "fly", draw: () => { P("M6 52 L92 14 L66 84 L50 60 L28 68Z", "w", "k", 4); line("M92 14 L50 60", "k", 3); P("M50 60 L52 78 L62 66Z", "s", "k", 2); } },
  book: { idle: "pulse", draw: () => { P("M8 22 H48 V84 H8Z", "a", "k", 4); P("M52 22 H92 V84 H52Z", "b", "k", 4); P("M16 34 H40 M16 46 H40 M16 58 H34 M60 34 H84 M60 46 H84 M60 58 H78", null, "w", 3.5); } },
  bolt: { idle: "pulse", draw: (t) => { glow(50, 50, 50, "rgba(255,220,60,0.8)", 0.5 + 0.3 * Math.sin(t * 8)); P("M58 4 L20 56 H46 L38 96 L80 40 H54Z", "y", "Y", 4); } },
  trophy: { idle: "bob", draw: () => {
    line("M28 20 H12 C12 40 22 48 32 48 M72 20 H88 C88 40 78 48 68 48", "Y", 6);
    P("M26 8 H74 V38 C74 56 62 66 50 66 C38 66 26 56 26 38Z", "y", "Y", 4); P("M44 66 H56 V78 H44Z", "Y"); P("M30 80 H70 V92 H30Z", "k");
  } },
  fire: { idle: "flicker", draw: () => { P("M50 4 C54 24 78 34 78 60 C78 80 66 94 50 94 C34 94 22 80 22 60 C22 46 30 40 34 28 C38 36 42 40 46 40 C46 28 46 16 50 4Z", "o", "k", 3); P("M50 50 C58 62 66 68 66 78 C66 87 58 92 50 92 C42 92 34 87 34 78 C34 68 44 62 50 50Z", "y"); } },
  drop: { idle: "bob", draw: () => { P("M50 6 C50 6 18 46 18 64 C18 82 32 94 50 94 C68 94 82 82 82 64 C82 46 50 6 50 6Z", "u", "k", 4); P("M32 62 C32 72 38 80 46 82", null, "w", 4); } },
  chat: { idle: "pulse", draw: (t) => { P("M10 14 H90 V68 H44 L24 88 V68 H10Z", "b", "k", 4); [30, 50, 70].forEach((x, i) => circ(x, 41 + Math.sin(t * 6 + i) * 3, 5, "w")); } },
  mail: { idle: "bob", draw: () => { P("M6 22 H94 V78 H6Z", "w", "k", 4); line("M6 24 L50 58 L94 24", "k", 4); } },
  camera: { idle: "pulse", draw: () => { P("M6 30 H28 L34 20 H66 L72 30 H94 V82 H6Z", "k"); circ(50, 56, 22, "u", "w", 4); circ(50, 56, 10, "k"); circ(80, 40, 3.5, "r"); } },
  flask: { idle: "swing", draw: (t) => {
    P("M38 8 H62 V34 L88 82 C92 90 88 94 80 94 H20 C12 94 8 90 12 82 L38 34Z", "l", "k", 4);
    ctx.save(); ctx.clip(new Path2D("M38 8 H62 V34 L88 82 C92 90 88 94 80 94 H20 C12 94 8 90 12 82 L38 34Z")); P("M0 66 H100 V100 H0Z", "g");
    for (let i = 0; i < 3; i++) circ(36 + i * 14, 84 - ((t * 20 + i * 11) % 24), 3 + i, "w"); ctx.restore();
  } },
  pin: { idle: "bob", draw: () => { P("M50 94 C50 94 18 58 18 36 C18 18 32 6 50 6 C68 6 82 18 82 36 C82 58 50 94 50 94Z", "r", "k", 4); circ(50, 36, 12, "w", "k", 3); } },
  users: { idle: "bob", draw: () => {
    P("M2 90 C2 70 14 62 26 62 C38 62 50 70 50 90Z", "a", "k", 3); circ(26, 44, 12, "#f2c49b", "k", 3);
    P("M50 90 C50 70 62 62 74 62 C86 62 98 70 98 90Z", "b", "k", 3); circ(74, 44, 12, "#e8b48a", "k", 3);
    P("M24 94 C24 72 36 62 50 62 C64 62 76 72 76 94Z", "g", "k", 3); circ(50, 40, 14, "#f2c49b", "k", 3);
  } },
  battery: { idle: "none", draw: (t) => {
    P("M8 28 H84 V72 H8Z", "w", "k", 4); P("M84 42 H94 V58 H84Z", "k"); const f = 0.2 + 0.8 * eInOut(seg((t * 0.5) % 1.4, 0, 1));
    P(`M13 33 H${13 + 66 * f} V67 H13Z`, f > 0.5 ? "g" : "o");
  } },
  wifi: { idle: "none", draw: (t) => { [38, 26, 14].forEach((r, i) => { ctx.globalAlpha = 0.25 + 0.75 * clamp(Math.sin(t * 4 - i * 0.9) * 0.5 + 0.7); line(`M${50 - r} ${78 - r * 0.9}A${r * 1.2} ${r * 1.2} 0 0 1 ${50 + r} ${78 - r * 0.9}`, "b", 8); }); ctx.globalAlpha = 1; circ(50, 80, 7, "b"); } },
  chip: { idle: "pulse", draw: (t) => {
    for (let i = 0; i < 5; i++) { P(`M${24 + i * 14} 6V22M${24 + i * 14} 78V94M6 ${24 + i * 14}H22M78 ${24 + i * 14}H94`, null, "s", 4); }
    P("M20 20 H80 V80 H20Z", "k", "s", 3); P("M34 34 H66 V66 H34Z", "b"); glow(50, 50, 30, hexA(TH.alt, 0.9), 0.4 + 0.3 * Math.sin(t * 5));
  } },
};
ICONS.coins = ICONS.coin; ICONS.money = ICONS.coin; ICONS.idea = ICONS.bulb; ICONS.time = ICONS.clock; ICONS.love = ICONS.heart; ICONS.security = ICONS.shield;
ICONS.shop = ICONS.cart; ICONS.home = ICONS.house; ICONS.settings = ICONS.gear; ICONS.world = ICONS.globe; ICONS.chart = ICONS.growth;
ICONS.search = ICONS.magnifier; ICONS.user = ICONS.person; ICONS.computer = ICONS.laptop; ICONS.weather = ICONS.cloud; ICONS.energy = ICONS.bolt;
ICONS.win = ICONS.trophy; ICONS.water = ICONS.drop; ICONS.message = ICONS.chat; ICONS.email = ICONS.mail; ICONS.science = ICONS.flask;
ICONS.map = ICONS.pin; ICONS.people = ICONS.users; ICONS.internet = ICONS.wifi; ICONS.tech = ICONS.chip; ICONS.travel = ICONS.plane;

function drawIcon(name, x, y, size, o) {
  const ic = ICONS[name] || ICONS.star, t = o.t || 0;
  ctx.save(); ctx.translate(x, y); ctx.scale(size / 100, size / 100);
  if (o.flip) ctx.scale(-1, 1);
  if (o.rot) ctx.rotate(o.rot);
  const idle = o.idle || ic.idle;
  if (idle === "bob") ctx.translate(0, Math.sin(t * 2.4) * 3);
  else if (idle === "pulse") ctx.scale(1 + 0.05 * Math.sin(t * 3), 1 + 0.05 * Math.sin(t * 3));
  else if (idle === "beat") { const k = Math.pow(Math.max(0, Math.sin(t * 5)), 6); ctx.scale(1 + 0.14 * k, 1 + 0.14 * k); }
  else if (idle === "swing") ctx.rotate(Math.sin(t * 2) * 0.12);
  else if (idle === "spin") ctx.rotate(Math.sin(t * 1.5) * 0.25);
  else if (idle === "fly") ctx.translate(Math.sin(t * 2) * 3, -Math.sin(t * 2) * 3);
  else if (idle === "flicker") ctx.scale(1, 1 + 0.04 * Math.sin(t * 17));
  ctx.translate(-50, -50);
  if (o.shadow) { ctx.save(); ctx.globalAlpha = 0.18; ctx.fillStyle = "#000"; ctx.beginPath(); ctx.ellipse(50, 98, 30, 5, 0, 0, TAU); ctx.fill(); ctx.restore(); }
  ic.draw(t); ctx.restore();
}

/* ---------- the API handed to AI-written scene code ---------- */
const WEIGHTS = { black: [FONT.black, 400], bold: [FONT.bold, 700], med: [FONT.med, 500], serif: [FONT.serif, 400] };
function makeApi(th) {
  TH = th;
  const Wd = W / U, Hd = H / U;
  return {
    ctx, W: Wd, H: Hd, th, PI2: TAU, icons: Object.keys(ICONS),
    ease: { out: eOut, inOut: eInOut, back: eBack, elastic: eElastic, in: (t) => clamp(t) * clamp(t) * clamp(t) },
    seg, lerp, clamp, rng, hex: hexA, project: (x, y, z, cam) => project(x, y, z, cam),
    bg: (c, c2) => {
      if (c2) { const gr = ctx.createLinearGradient(0, 0, 0, Hd); gr.addColorStop(0, c); gr.addColorStop(1, c2); ctx.fillStyle = gr; } else ctx.fillStyle = c || th.bg;
      ctx.fillRect(-10, -10, Wd + 20, Hd + 20);
    },
    grad: (x0, y0, x1, y1, stops) => { const gr = ctx.createLinearGradient(x0, y0, x1, y1); stops.forEach((c, i) => gr.addColorStop(i / Math.max(1, stops.length - 1), c)); return gr; },
    rrect: (x, y, w, h, r) => rrect(x, y, w, h, r),
    glow: (x, y, r, color, a) => glow(x, y, r, color, a == null ? 1 : a),
    path: (d) => new Path2D(String(d).slice(0, 4000)),
    fit: (str, weight, maxW, maxSize) => fit(String(str), (WEIGHTS[weight] || WEIGHTS.black)[0], (WEIGHTS[weight] || WEIGHTS.black)[1], maxW, maxSize),
    text: (str, x, y, size, color, o = {}) => {
      const [fam, wt] = WEIGHTS[o.font] || WEIGHTS.black;
      text(String(str), x, y, size, fam, color || th.fg, { ...o, weight: wt, sd: (o.sd || 0) / U });
    },
    icon: (name, x, y, size, o = {}) => drawIcon(String(name), x, y, size, o),
    grid: (t, color, gap = 60, a = 0.15) => {
      ctx.save(); ctx.fillStyle = hexA(color || th.fg, a); const off = (t * 14) % gap;
      for (let y = -gap + off; y < Hd + gap; y += gap) for (let x = -gap + off; x < Wd + gap; x += gap) { ctx.beginPath(); ctx.arc(x, y, 3, 0, TAU); ctx.fill(); }
      ctx.restore();
    },
    stars: (t, seed = 1, n = 80, color = "#ffffff") => {
      const r = rng(seed); ctx.save();
      for (let i = 0; i < n; i++) { const x = r() * Wd, y = r() * Hd, s = 1 + r() * 3, ph = r() * TAU; ctx.globalAlpha = 0.35 + 0.65 * (Math.sin(t * (1 + r() * 2) + ph) * 0.5 + 0.5); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, s, 0, TAU); ctx.fill(); }
      ctx.restore();
    },
    sunburst: (t, cx, cy, rays = 18, color) => {
      const R = Math.hypot(Wd, Hd); ctx.save(); ctx.translate(cx, cy); ctx.rotate(t * 0.12); ctx.fillStyle = color || th.soft;
      for (let i = 0; i < rays; i += 2) { ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, R, (i / rays) * TAU, ((i + 1) / rays) * TAU); ctx.closePath(); ctx.fill(); }
      ctx.restore();
    },
  };
}
const DENY = /\b(fetch|XMLHttpRequest|WebSocket|import|require|eval|Function|document|window|globalThis|self|localStorage|sessionStorage|navigator|location|Worker|setTimeout|setInterval|requestAnimationFrame|constructor|__proto__|prototype|while|canvas|ownerDocument|defaultView|getPrototypeOf|Reflect|Proxy|Object|Date)\b/;
window.compileScene = function (code) {
  if (typeof code !== "string" || code.length > 12000 || DENY.test(code) || /for\s*\([^)]*;\s*;/.test(code)) return null;
  try { return new Function("g", "t", "d", `"use strict";\n${code}`); } catch (e) { return null; }
};

/* ---------- template scenes that use the icons ---------- */
SCENES.icon = function (t, d, data, th) {
  bg(th); floatBlobs(t, th); TH = th;
  const cx = W / 2, cy = contentH() * 0.42, S = Math.min(W * 0.62, contentH() * 0.42);
  const pop = eElastic(seg(t, 0.05, 0.9));
  glow(cx, cy, S * 0.9, hexA(th.accent, 0.5), th.dark ? 0.7 : 0.35);
  const r = rng(4);
  for (let i = 0; i < 10; i++) { const a = r() * TAU + t * 0.4, dd = S * (0.65 + r() * 0.35), k = (t * 0.5 + r()) % 1; ctx.fillStyle = hexA(i % 2 ? th.accent : th.alt, 0.8 * (1 - k)); ctx.beginPath(); ctx.arc(cx + Math.cos(a) * dd, cy + Math.sin(a) * dd, (5 + r() * 8) * U * (1 - k * 0.5), 0, TAU); ctx.fill(); }
  drawIcon(data.icon, cx, cy, S * pop, { t, shadow: true });
  const label = (data.text || "").toUpperCase();
  if (label) text(label, W / 2, contentH() * 0.8, fit(label, FONT.black, 400, W * 0.86, 120 * U), FONT.black, th.fg, { weight: 400, scale: lerp(0.7, 1, eBack(seg(t, 0.5, 1.1))), alpha: eOut(seg(t, 0.4, 0.8)) });
  if (data.sub) text(data.sub, W / 2, contentH() * 0.8 + 90 * U, 52 * U, FONT.serif, th.fg, { alpha: eOut(seg(t, 1, 1.5)) * 0.85 });
};
SCENES.iconrow = function (t, d, data, th) {
  bg(th); dotGrid(t, th, 0.12); TH = th;
  const items = (data.items || []).slice(0, 4), n = items.length || 1, zone = contentH();
  if (data.title) text(data.title.toUpperCase(), W / 2, zone * 0.14, fit(data.title.toUpperCase(), FONT.black, 400, W * 0.86, 110 * U), FONT.black, th.fg, { weight: 400, alpha: eOut(seg(t, 0, 0.5)), scale: lerp(0.8, 1, eBack(seg(t, 0, 0.6))) });
  const portrait = H > W, cols = portrait ? 1 : n, rows = portrait ? n : 1, cw = (W * 0.9) / cols, chh = (zone * 0.72) / rows;
  items.forEach((it, i) => {
    const c = portrait ? 0 : i, rr = portrait ? i : 0, p = eBack(seg(t, 0.4 + i * 0.3, 1.0 + i * 0.3));
    const x = W * 0.05 + cw * (c + 0.5), y = zone * 0.26 + chh * (rr + 0.5), size = Math.min(cw, chh) * (portrait ? 0.8 : 0.55);
    ctx.save(); ctx.globalAlpha = clamp(p * 2);
    if (portrait) { ctx.fillStyle = th.dark ? th.soft : "#ffffff"; ctx.shadowColor = "rgba(0,0,0,0.2)"; ctx.shadowBlur = 20 * U; rrect(W * 0.07, y - chh * 0.45, W * 0.86, chh * 0.9, chh * 0.2); ctx.fill(); ctx.shadowColor = "transparent"; }
    ctx.restore();
    const ix = portrait ? W * 0.07 + chh * 0.5 : x, iy = portrait ? y : y - size * 0.1;
    drawIcon(it.icon, ix, iy, size * p * (portrait ? 0.8 : 1), { t: t - i * 0.2 });
    const lab = String(it.label || "").toUpperCase(), lx = portrait ? W * 0.07 + chh * 1.05 : x, ly = portrait ? y : y + size * 0.62;
    text(lab, lx, ly, fit(lab, FONT.black, 400, portrait ? W * 0.86 - chh * 1.2 : cw * 0.92, portrait ? chh * 0.34 : 70 * U), FONT.black, th.fg, { weight: 400, align: portrait ? "left" : "center", alpha: clamp(p * 2) });
  });
};
