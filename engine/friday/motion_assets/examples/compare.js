const ctx = g.ctx, W = g.W, H = g.H, th = g.th, e = g.ease;
g.bg(th.bg); g.glow(W * 0.25, H * 0.5, 600, g.hex(th.accent, 0.5), 0.35); g.glow(W * 0.75, H * 0.5, 600, g.hex(th.alt, 0.5), 0.35);
const wide = W > H, cw = wide ? W * 0.38 : W * 0.8, ch = wide ? H * 0.62 : H * 0.34;
const cards = [{ name: "RENT", icon: "house", color: th.accent, pts: ["Flexible", "Low upfront"] }, { name: "BUY", icon: "coin", color: th.alt, pts: ["Build equity", "Fixed payments"] }];
cards.forEach((c, i) => {
  const p = e.back(g.seg(t, 0.15 + i * 0.35, 0.85 + i * 0.35));
  const cx = wide ? W * (i ? 0.73 : 0.27) : W / 2, cy = wide ? H * 0.5 : H * (i ? 0.7 : 0.29);
  ctx.save(); ctx.translate(cx, cy + (1 - p) * 140); ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p); ctx.globalAlpha = g.clamp(p * 1.5);
  ctx.fillStyle = th.dark ? th.soft : "#ffffff"; ctx.shadowColor = "rgba(0,0,0,0.3)"; ctx.shadowBlur = 40; ctx.shadowOffsetY = 16;
  g.rrect(-cw / 2, -ch / 2, cw, ch, 50); ctx.fill(); ctx.shadowColor = "transparent";
  ctx.fillStyle = c.color; g.rrect(-cw / 2, -ch / 2, cw, 14, 7); ctx.fill();
  g.icon(c.icon, -cw / 2 + ch * 0.28, -ch * 0.08, ch * 0.34, { t: t - i * 0.3 });
  g.text(c.name, cw * 0.14, -ch * 0.12, Math.min(110, ch * 0.3), c.color, { align: "center" });
  c.pts.forEach((pt, k) => {
    const q = e.out(g.seg(t, 0.9 + i * 0.35 + k * 0.25, 1.4 + i * 0.35 + k * 0.25));
    g.text("✓", -cw / 2 + 70, ch * 0.2 + k * ch * 0.17, 54, c.color, { font: "bold", align: "left", alpha: q });
    g.text(pt, -cw / 2 + 130, ch * 0.2 + k * ch * 0.17, 54, th.dark ? th.fg : "#17140f", { font: "bold", align: "left", alpha: q });
  });
  ctx.restore();
});
const vs = e.elastic(g.seg(t, 0.6, 1.3));
ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(vs, vs); ctx.fillStyle = th.fg; ctx.beginPath(); ctx.arc(0, 0, 62, 0, g.PI2); ctx.fill();
g.text("VS", 0, 4, 54, th.bg); ctx.restore();
