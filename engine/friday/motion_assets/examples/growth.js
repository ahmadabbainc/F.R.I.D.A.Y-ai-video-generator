const ctx = g.ctx, W = g.W, H = g.H, th = g.th, e = g.ease;
g.bg(th.bg); g.grid(t, th.fg, 64, 0.1);
const bars = [["2019", 22], ["2020", 38], ["2021", 55], ["2022", 78], ["2023", 100]];
const bw = 130, gap = 70, total = bars.length * bw + (bars.length - 1) * gap;
const x0 = W / 2 - total / 2, base = H * 0.76, maxH = Math.min(H * 0.38, 640);
ctx.fillStyle = g.hex(th.fg, 0.25); ctx.fillRect(x0 - 30, base, total + 60, 6);
bars.forEach(([label, v], i) => {
  const p = e.back(g.seg(t, 0.3 + i * 0.22, 0.9 + i * 0.22)), h = (v / 100) * maxH * p, x = x0 + i * (bw + gap);
  ctx.fillStyle = i === bars.length - 1 ? th.accent : th.alt;
  g.rrect(x, base - h, bw, Math.max(h, 1), 18); ctx.fill();
  g.text(label, x + bw / 2, base + 60, 64, th.fg, { font: "bold", alpha: g.clamp(p * 2) });
});
const wob = Math.sin(t * 2.2) * 6;
const count = Math.round(100 * e.inOut(g.seg(t, 0.4, 1.9)));
g.text(count + "%", W * 0.42, H * 0.17 + wob, 220, th.fg, { scale: 0.85 + 0.15 * e.back(g.seg(t, 0, 0.6)) });
g.text("GROWTH", W * 0.42, H * 0.17 + 150, 80, th.accent, { font: "bold", alpha: e.out(g.seg(t, 0.6, 1.1)) });
g.icon("growth", W * 0.86, H * 0.17, 190, { t });
