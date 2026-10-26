const ctx = g.ctx, W = g.W, H = g.H, th = g.th, e = g.ease;
g.bg(th.bg); g.grid(t, th.fg, 64, 0.1);
const bars = [["2019", 22], ["2020", 38], ["2021", 55], ["2022", 78], ["2023", 100]];
const bw = Math.min(150, W / 8), gap = bw * 0.45, total = bars.length * bw + (bars.length - 1) * gap;
const x0 = W / 2 - total / 2, base = H * 0.72, maxH = Math.min(H * 0.38, 620);
ctx.fillStyle = g.hex(th.fg, 0.25); ctx.fillRect(x0 - 30, base, total + 60, 6);
bars.forEach(([label, v], i) => {
  const p = e.back(g.seg(t, 0.3 + i * 0.22, 0.9 + i * 0.22)), h = (v / 100) * maxH * p, x = x0 + i * (bw + gap);
  ctx.fillStyle = i === bars.length - 1 ? th.accent : th.alt;
  g.rrect(x, base - h, bw, Math.max(h, 1), 18); ctx.fill();
  ctx.fillStyle = g.hex("#ffffff", 0.25); g.rrect(x + 10, base - h + 10, 18, Math.max(h - 20, 0), 9); ctx.fill();
  g.text(label, x + bw / 2, base + 46, 38, th.fg, { font: "bold", alpha: g.clamp(p * 2) });
});
const count = Math.round(100 * e.inOut(g.seg(t, 0.4, 1.9)));
g.text(count + "%", W * 0.4, H * 0.17, 190, th.fg, { scale: 0.85 + 0.15 * e.back(g.seg(t, 0, 0.6)) });
g.text("GROWTH", W * 0.4, H * 0.17 + 120, 56, th.accent, { font: "bold", alpha: e.out(g.seg(t, 0.6, 1.1)) });
g.icon("growth", W * 0.86, H * 0.17, 170, { t });
