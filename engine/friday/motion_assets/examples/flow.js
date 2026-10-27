const ctx = g.ctx, W = g.W, H = g.H, th = g.th, e = g.ease, wide = W > H;
g.bg(th.bg, th.soft); g.grid(t, th.fg, 70, 0.1);
g.text("HOW IT FLOWS", W / 2, H * 0.09, g.fit("HOW IT FLOWS", "black", W * 0.86, 140), th.fg, { scale: 0.7 + 0.3 * e.back(g.seg(t, 0, 0.6)), alpha: e.out(g.seg(t, 0, 0.4)) });
const steps = [["laptop", "INPUT"], ["gear", "PROCESS"], ["trophy", "RESULT"]];
const pts = steps.map((s, i) => wide ? [W * (0.2 + i * 0.3), H * 0.52] : [W * 0.3, H * (0.25 + i * 0.27)]);
for (let i = 0; i < 2; i++) {
  const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], k = e.inOut(g.seg(t, 0.6 + i * 0.7, 1.4 + i * 0.7));
  ctx.strokeStyle = g.hex(th.fg, 0.25); ctx.lineWidth = 10; ctx.setLineDash([26, 22]); ctx.lineDashOffset = -t * 60;
  ctx.beginPath(); ctx.moveTo(x0, y0 + (wide ? 0 : 150)); ctx.lineTo(x0 + (x1 - x0) * k, y0 + (wide ? 0 : 150) + (y1 - y0 - (wide ? 0 : 300)) * k); ctx.stroke(); ctx.setLineDash([]);
  if (k >= 1) for (let n = 0; n < 3; n++) { const u = (t * 0.7 + n / 3) % 1; ctx.fillStyle = th.accent; ctx.beginPath(); ctx.arc(x0 + (x1 - x0) * u, y0 + (wide ? 0 : 150) + (y1 - y0 - (wide ? 0 : 300)) * u, 14, 0, g.PI2); ctx.fill(); }
}
steps.forEach(([icon, label], i) => {
  const p = e.back(g.seg(t, 0.3 + i * 0.6, 1.0 + i * 0.6)), [x, y] = pts[i];
  g.glow(x, y, 260, g.hex(i % 2 ? th.alt : th.accent, 0.6), 0.45 * g.clamp(p));
  g.icon(icon, x, y, 280 * p, { t: t - i * 0.3, shadow: true });
  g.text(label, wide ? x : x + 190, wide ? y + 230 : y, 90, th.fg, { alpha: g.clamp(p * 2), align: wide ? "center" : "left" });
});
