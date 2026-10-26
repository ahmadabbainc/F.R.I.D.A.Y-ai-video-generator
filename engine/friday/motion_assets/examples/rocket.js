const ctx = g.ctx, W = g.W, H = g.H, e = g.ease;
g.bg("#070b1f", "#22307a");
g.stars(t, 3, 110);
const moon = e.out(g.seg(t, 0, 1.6)), mx = W * 0.72, my = H * 0.22 + (1 - moon) * 160;
g.glow(mx, my, 380, "rgba(190,215,255,0.9)", 0.35 * moon);
ctx.fillStyle = "#e8edf7"; ctx.beginPath(); ctx.arc(mx, my, 150, 0, g.PI2); ctx.fill();
ctx.fillStyle = "#c5cde0";
[[-50, -30, 38], [40, 10, 26], [-20, 60, 20]].forEach(([x, y, r]) => { ctx.beginPath(); ctx.arc(mx + x, my + y, r, 0, g.PI2); ctx.fill(); });
const fly = e.inOut(g.seg(t, 0.3, Math.max(2.2, d - 0.6)));
const rx = W / 2 + Math.sin(t * 1.8) * 14, ry = H * 0.88 - fly * H * 0.5;
const r = g.rng(5);
for (let i = 0; i < 22; i++) {
  const age = (t * 0.9 + i / 22) % 1;
  ctx.globalAlpha = (1 - age) * 0.55 * e.out(g.seg(t, 0.3, 0.8)); ctx.fillStyle = "#ffffff";
  ctx.beginPath(); ctx.arc(rx + (r() - 0.5) * 90 * age, ry + 150 + age * 440, 26 + age * 60, 0, g.PI2); ctx.fill();
}
ctx.globalAlpha = 1;
g.icon("rocket", rx, ry, 400, { t });
const label = "TO THE MOON";
g.text(label, W / 2, H * 0.1, g.fit(label, "black", W * 0.86, 150), "#ffffff", { scale: 0.7 + 0.3 * e.back(g.seg(t, 0.2, 0.9)), alpha: e.out(g.seg(t, 0.1, 0.5)) });
