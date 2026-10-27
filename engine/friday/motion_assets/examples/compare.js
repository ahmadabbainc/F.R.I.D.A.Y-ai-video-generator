const ctx = g.ctx, W = g.W, H = g.H, th = g.th, e = g.ease;
g.bg(th.bg); g.glow(W * 0.25, H * 0.3, 700, g.hex(th.accent, 0.6), 0.4); g.glow(W * 0.75, H * 0.7, 700, g.hex(th.alt, 0.6), 0.4);
const wide = W > H;
const sides = [{ name: "RENT", icon: "house", color: th.accent }, { name: "BUY", icon: "coin", color: th.alt }];
sides.forEach((c, i) => {
  const p = e.back(g.seg(t, 0.15 + i * 0.4, 0.85 + i * 0.4));
  const cx = wide ? W * (i ? 0.76 : 0.24) : W / 2, cy = wide ? H * 0.42 : H * (i ? 0.73 : 0.24);
  const size = wide ? 440 : 480;
  ctx.save(); ctx.globalAlpha = g.clamp(p * 1.5);
  g.glow(cx, cy, size * 0.8, g.hex(c.color, 0.7), 0.5);
  g.icon(c.icon, cx, cy + (1 - p) * 120, size * (0.5 + 0.5 * p), { t: t - i * 0.4, shadow: true });
  g.text(c.name, cx, cy + size * 0.68, 160, c.color, { scale: 0.6 + 0.4 * p });
  ctx.restore();
});
const vs = e.elastic(g.seg(t, 0.7, 1.4));
ctx.save(); ctx.translate(W / 2, H / 2 - (wide ? 0 : 0)); ctx.scale(vs, vs); ctx.rotate(Math.sin(t * 2) * 0.05);
ctx.fillStyle = th.fg; ctx.beginPath(); ctx.arc(0, 0, 84, 0, g.PI2); ctx.fill();
g.text("VS", 0, 4, 80, th.bg, { keepColor: true }); ctx.restore();
