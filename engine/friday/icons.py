"""Animated icons, drawn from shapes. Each icon is a function

    icon(cv, cx, cy, s, p, t)

cv: Canvas, (cx, cy): centre, s: half-size in pixels, p: pop-in progress 0..1,
t: seconds since the scene began (drives the idle motion).
Shapes are designed in a unit box of -1..1 and scaled by s.
"""

from __future__ import annotations

import math
import re

from .draw import ACCENT, BG_BOTTOM, CARD, CYAN, GREEN, MUTED, TEXT, VIOLET, Canvas, clamp01, ease_back, ease_out

DARK = (24, 22, 52)
ORANGE = (255, 122, 61)
PINK = (255, 107, 138)


def _scale(s: float, p: float) -> float:
    return s * max(0.0, ease_back(clamp01(p)))


def _pts(cx, cy, s):
    return lambda x, y: (cx + x * s, cy + y * s)


def rocket(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    rise = (1 - ease_out(clamp01(p))) * 1.2  # flies up into place, then hovers
    bob = math.sin(t * 3.2) * 0.04
    P = _pts(cx, cy + (rise + bob) * s, k)
    for i in range(7):  # exhaust puffs
        f = (t * 1.6 + i / 7) % 1.0
        cv.circle(*P(math.sin(i * 2.3) * 0.16, 0.75 + f * 1.0), (0.1 + 0.08 * f) * k, (255, 200, 120) if i % 2 else TEXT, (1 - f) * 0.55)
    fl = 0.42 + 0.14 * math.sin(t * 28) + 0.06 * math.sin(t * 17)
    cv.polygon([P(-0.2, 0.55), P(0, 0.55 + fl), P(0.2, 0.55)], ORANGE)
    cv.polygon([P(-0.1, 0.55), P(0, 0.55 + fl * 0.6), P(0.1, 0.55)], ACCENT)
    cv.polygon([P(-0.26, 0.05), P(-0.62, 0.66), P(-0.2, 0.52)], PINK)
    cv.polygon([P(0.26, 0.05), P(0.62, 0.66), P(0.2, 0.52)], PINK)
    body = [(0, -0.82), (0.14, -0.64), (0.25, -0.36), (0.3, -0.05), (0.28, 0.3), (0.22, 0.56),
            (-0.22, 0.56), (-0.28, 0.3), (-0.3, -0.05), (-0.25, -0.36), (-0.14, -0.64)]
    cv.polygon([P(*q) for q in body], TEXT)
    cv.polygon([P(0, -0.82), P(0.14, -0.64), P(0.25, -0.38), P(-0.25, -0.38), P(-0.14, -0.64)], PINK)
    cv.circle(*P(0, -0.04), 0.17 * k, DARK)
    cv.circle(*P(0, -0.04), 0.12 * k, CYAN)
    cv.circle(*P(-0.04, -0.08), 0.04 * k, TEXT, 0.8)


def coins(cv, cx, cy, s, p, t):
    k = s
    P = _pts(cx, cy, k)
    for i in range(4):  # a stack of coins dropping in one after another
        pi = clamp01(p * 1.8 - i * 0.3)
        drop = (1 - ease_out(pi)) * -1.4
        wob = math.sin(t * 4 + i) * 0.012
        y = 0.55 - i * 0.24 + drop + wob
        if pi <= 0:
            continue
        cv.rrect(*P(-0.62, y - 0.1), *P(0.62, y + 0.12), 0.11 * k, (214, 150, 20), pi)
        cv.rrect(*P(-0.62, y - 0.17), *P(0.62, y + 0.05), 0.11 * k, ACCENT, pi)
        cv.rrect(*P(-0.46, y - 0.12), *P(0.46, y - 0.04), 0.04 * k, (255, 217, 130), pi * 0.8)
    top = clamp01(p * 1.8 - 1.2)
    if top > 0:  # a big coin spins on top
        w = abs(math.cos(t * 2.4)) * 0.5 + 0.12
        yy = -0.5 + math.sin(t * 3) * 0.05
        cv.circle(*P(0, yy), 0.4 * k, (214, 150, 20), top)
        cv.rrect(*P(-w, yy - 0.4), *P(w, yy + 0.4), w * k, ACCENT, top)
        if w > 0.32:
            cv.text(P(0, yy), "$", 0.5 * k, DARK, True, "mm", top)


def bulb(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    P = _pts(cx, cy, k)
    glow = 0.55 + 0.25 * math.sin(t * 3)
    from .draw import soft_glow
    soft_glow(cv, cx, cy - 0.15 * k, 1.9 * k, ACCENT, glow * 0.6)
    for i in range(10):  # rays turn slowly and breathe
        a = i / 10 * math.tau + t * 0.6
        r0, r1 = 0.78, 0.98 + 0.1 * math.sin(t * 4 + i)
        cv.line([P(math.cos(a) * r0, -0.2 + math.sin(a) * r0), P(math.cos(a) * r1, -0.2 + math.sin(a) * r1)], 0.07 * k, ACCENT, 0.9)
    cv.circle(*P(0, -0.2), 0.5 * k, ACCENT)
    cv.rrect(*P(-0.24, 0.1), *P(0.24, 0.52), 0.06 * k, ACCENT)
    cv.circle(*P(-0.16, -0.36), 0.12 * k, (255, 240, 200), 0.8)
    for j, y in enumerate((0.5, 0.64, 0.78)):
        cv.rrect(*P(-0.22 + j * 0.02, y - 0.05), *P(0.22 - j * 0.02, y + 0.07), 0.05 * k, MUTED if j % 2 else TEXT)
    cv.line([P(-0.12, 0.05), P(-0.12, -0.12), P(0, 0.0), P(0.12, -0.12), P(0.12, 0.05)], 0.05 * k, DARK, 0.8)


def clock(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    P = _pts(cx, cy, k)
    cv.circle(cx, cy, k * 0.96, VIOLET)
    cv.circle(cx, cy, k * 0.82, TEXT)
    for i in range(12):
        a = i / 12 * math.tau
        r0 = 0.66 if i % 3 == 0 else 0.72
        cv.line([P(math.sin(a) * r0, -math.cos(a) * r0), P(math.sin(a) * 0.78, -math.cos(a) * 0.78)], 0.045 * k, DARK)
    for length, speed, width, col in ((0.5, 0.35, 0.09, DARK), (0.7, 4.2, 0.06, ACCENT)):
        a = t * speed
        cv.line([P(0, 0), P(math.sin(a) * length, -math.cos(a) * length)], width * k, col)
    cv.circle(cx, cy, 0.07 * k, DARK)
    for sx in (-1, 1):  # little bells that jiggle
        j = math.sin(t * 22) * 0.04
        cv.circle(*P(sx * (0.62 + j), -0.78), 0.2 * k, PINK)


def heart(cv, cx, cy, s, p, t):
    beat = 1 + 0.12 * max(0.0, math.sin(t * 6.5)) ** 3 + 0.05 * max(0.0, math.sin(t * 6.5 - 1.2)) ** 3
    k = _scale(s, p) * beat
    pts = []
    for i in range(48):
        a = i / 48 * math.tau
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x / 17 * k, cy + (y + 2) / 17 * k))
    from .draw import soft_glow
    soft_glow(cv, cx, cy, 1.7 * k, PINK, 0.35)
    cv.polygon(pts, PINK)
    cv.polygon([(cx + (x - cx) * 0.55 - 0.18 * k, cy + (y - cy) * 0.4 - 0.32 * k) for x, y in pts[:14]], (255, 170, 190), 0.55)


def shield(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    P = _pts(cx, cy + math.sin(t * 2.2) * 0.03 * s, k)
    pts = [P(0, -0.95), P(0.75, -0.7), P(0.75, 0.0), P(0.6, 0.45), P(0, 0.98), P(-0.6, 0.45), P(-0.75, 0.0), P(-0.75, -0.7)]
    cv.polygon(pts, CYAN)
    cv.polygon([P(0, -0.95), P(0.75, -0.7), P(0.75, 0.0), P(0.6, 0.45), P(0, 0.98)], (60, 170, 215))
    cv.polygon([P(0, -0.74), P(0.56, -0.54), P(0.56, -0.02), P(0.45, 0.34), P(0, 0.76), P(-0.45, 0.34), P(-0.56, -0.02), P(-0.56, -0.54)], DARK, 0.35)
    draw = clamp01((t - 0.4) * 1.8)
    path = [P(-0.3, 0.0), P(-0.08, 0.24), P(0.34, -0.26)]
    n = draw * 2
    shown = path[: int(n) + 1] + ([(path[int(n)][0] + (path[int(n) + 1][0] - path[int(n)][0]) * (n - int(n)),
                                    path[int(n)][1] + (path[int(n) + 1][1] - path[int(n)][1]) * (n - int(n)))] if int(n) < 2 else [])
    if len(shown) >= 2:
        cv.line(shown, 0.13 * k, TEXT)
    sh = (t * 0.7) % 1.6  # a glint sweeps across
    if sh < 1:
        cv.line([P(-0.7 + sh * 1.4, -0.7), P(-0.9 + sh * 1.4, 0.2)], 0.1 * k, TEXT, 0.25)


def lock(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    P = _pts(cx, cy, k)
    open_amt = 0.5 + 0.5 * math.sin(t * 1.8)  # shackle opens and closes
    lift = open_amt * 0.22
    pts = [P(-0.34, -0.1 - lift)]
    pts += [P(math.cos(math.pi + i / 16 * math.pi) * 0.34, -0.1 - lift - math.sin(i / 16 * math.pi) * 0.5) for i in range(17)]
    pts.append(P(0.34, -0.1 - lift))
    cv.line(pts, 0.12 * k, MUTED)
    cv.rrect(*P(-0.62, -0.12), *P(0.62, 0.82), 0.16 * k, ACCENT)
    cv.rrect(*P(-0.62, 0.35), *P(0.62, 0.82), 0.16 * k, (214, 150, 20), 0.5)
    cv.circle(*P(0, 0.26), 0.12 * k, DARK)
    cv.rrect(*P(-0.04, 0.28), *P(0.04, 0.5), 0.03 * k, DARK)


def cart(cv, cx, cy, s, p, t):
    k = s
    slide = (1 - ease_out(clamp01(p))) * -2.2
    P = _pts(cx + slide * k, cy + math.sin(t * 7) * 0.012 * k, k)
    cv.line([P(-0.95, -0.7), P(-0.7, -0.7), P(-0.45, 0.35), P(0.6, 0.35)], 0.09 * k, MUTED)
    cv.polygon([P(-0.62, -0.45), P(0.85, -0.45), P(0.62, 0.2), P(-0.42, 0.2)], CYAN)
    for i in range(3):
        cv.line([P(-0.4 + i * 0.4, -0.4), P(-0.3 + i * 0.35, 0.15)], 0.04 * k, DARK, 0.4)
    for sx in (-0.3, 0.45):  # spinning wheels
        cv.circle(*P(sx, 0.62), 0.17 * k, TEXT)
        a = t * 8
        cv.line([P(sx - math.cos(a) * 0.13, 0.62 - math.sin(a) * 0.13), P(sx + math.cos(a) * 0.13, 0.62 + math.sin(a) * 0.13)], 0.03 * k, DARK)
    for i, c in enumerate((ACCENT, PINK, GREEN)):  # items hop into the basket
        f = clamp01(p * 2 - 0.9 - i * 0.2)
        hop = abs(math.sin((t * 2.2 + i * 0.7))) * 0.1
        if f > 0:
            cv.circle(*P(-0.3 + i * 0.4, -0.58 - hop), 0.14 * k, c, f)


def house(cv, cx, cy, s, p, t):
    k = s
    P = _pts(cx, cy + 0.05 * s, k)
    body = clamp01(p * 1.6)
    roof = ease_back(clamp01(p * 1.6 - 0.5))
    cv.rrect(*P(-0.66, -0.15 + (1 - ease_out(body)) * 0.9), *P(0.66, 0.78), 0.06 * k, TEXT, body)
    if roof > 0:
        dy = (1 - min(1, roof)) * -1.2
        cv.polygon([P(-0.88, -0.12 + dy), P(0, -0.82 + dy), P(0.88, -0.12 + dy)], PINK)
        cv.rrect(*P(0.34, -0.7 + dy), *P(0.5, -0.3 + dy), 0.02 * k, ACCENT)
    if body > 0.9:
        cv.rrect(*P(-0.14, 0.2), *P(0.2, 0.78), 0.05 * k, ACCENT)
        cv.circle(*P(0.14, 0.52), 0.025 * k, DARK)
        lit = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 2.5))
        for wx in (-0.5, 0.36):
            cv.rrect(*P(wx, -0.0), *P(wx + 0.2, 0.2), 0.03 * k, ACCENT, lit)
        cv.line([P(-0.9, 0.78), P(0.9, 0.78)], 0.06 * k, GREEN)


def gear(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    teeth, a0 = 10, t * 0.9
    pts = []
    for i in range(teeth * 4):
        a = a0 + i / (teeth * 4) * math.tau
        r = 0.98 if (i % 4) in (1, 2) else 0.74
        pts.append((cx + math.cos(a) * r * k, cy + math.sin(a) * r * k))
    cv.polygon(pts, VIOLET)
    cv.circle(cx, cy, 0.58 * k, (120, 104, 235))
    cv.circle(cx, cy, 0.3 * k, BG_BOTTOM)
    cv.ring(cx, cy, 0.3 * k, 0.05 * k, TEXT, 0.6)
    # a small gear meshing at the corner, turning the other way
    pts2 = []
    for i in range(32):
        a = -t * 1.35 + i / 32 * math.tau
        r = 0.4 if (i % 4) in (1, 2) else 0.28
        pts2.append((cx + 0.95 * k + math.cos(a) * r * k, cy + 0.82 * k + math.sin(a) * r * k))
    cv.polygon(pts2, CYAN)
    cv.circle(cx + 0.95 * k, cy + 0.82 * k, 0.11 * k, BG_BOTTOM)


def globe(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    cv.circle(cx, cy, k * 1.0, (36, 110, 190))
    cv.circle(cx, cy, k * 0.94, (52, 140, 220))
    spin = t * 0.7
    for lat in (-0.5, 0.0, 0.5):
        y = lat
        half = math.sqrt(max(0.0, 1 - y * y)) * 0.94
        cv.line([(cx - half * k, cy + y * 0.94 * k), (cx + half * k, cy + y * 0.94 * k)], 0.03 * k, TEXT, 0.35)
    for i in range(4):  # meridians sweep across as the globe turns
        lon = spin + i * math.pi / 4
        pts = [(cx + math.sin(a) * math.cos(lon) * 0.94 * k, cy - math.cos(a) * 0.94 * k) for a in [j / 24 * math.pi * 2 for j in range(25)]]
        cv.line(pts, 0.03 * k, TEXT, 0.4)
    for i, (lo, la) in enumerate(((0.3, -0.2), (2.4, 0.3), (4.4, -0.45), (5.6, 0.15))):  # continents drift past
        ang = lo + spin * 1.3
        vis = math.cos(ang)
        if vis > 0.1:
            x = math.sin(ang) * math.sqrt(1 - la * la) * 0.9
            cv.circle(cx + x * k, cy + la * 0.94 * k, (0.2 + 0.1 * (i % 2)) * k * vis, GREEN, 0.9 * min(1, vis * 2))
    cv.polygon([(cx - 0.55 * k, cy - 0.6 * k), (cx - 0.3 * k, cy - 0.78 * k), (cx - 0.1 * k, cy - 0.6 * k)], TEXT, 0.18)


def star(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    from .draw import soft_glow
    soft_glow(cv, cx, cy, 1.7 * k, ACCENT, 0.4 + 0.15 * math.sin(t * 3))
    a0 = t * 0.8
    pts = [(cx + math.sin(a0 + i * math.pi / 5) * (1.0 if i % 2 == 0 else 0.45) * k, cy - math.cos(a0 + i * math.pi / 5) * (1.0 if i % 2 == 0 else 0.45) * k)
           for i in range(10)]
    cv.polygon(pts, ACCENT)
    cv.polygon([(cx + (x - cx) * 0.55, cy + (y - cy) * 0.55) for x, y in pts], (255, 217, 130), 0.9)
    for i in range(5):  # sparkles
        f = (t * 0.9 + i / 5) % 1.0
        a = i * 2.4 + 0.5
        cv.circle(cx + math.cos(a) * (1.1 + f * 0.5) * k, cy + math.sin(a) * (1.1 + f * 0.5) * k, 0.07 * k * (1 - f), TEXT, 1 - f)


def growth(cv, cx, cy, s, p, t):
    k = s
    P = _pts(cx, cy, k)
    heights = (0.35, 0.6, 0.9, 1.3)
    for i, h in enumerate(heights):
        g = ease_out(clamp01(p * 2.2 - i * 0.28))
        x0 = -0.85 + i * 0.45
        top = 0.8 - h * g * 1.2
        cv.rrect(*P(x0, top), *P(x0 + 0.34, 0.8), 0.06 * k, GREEN if i == 3 else CYAN)
    pts = [P(-0.75, 0.3), P(-0.3, 0.05), P(0.15, -0.15), P(0.7, -0.62)]
    d = ease_out(clamp01((t - 0.5) / 1.0)) * 3
    shown = pts[: int(d) + 1]
    if int(d) < 3:
        a, b, f = pts[int(d)], pts[int(d) + 1], d - int(d)
        shown.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    if len(shown) >= 2:
        cv.line(shown, 0.09 * k, ACCENT)
        x, y = shown[-1]
        cv.circle(x, y, 0.1 * k, ACCENT)
        if d >= 3:
            cv.polygon([(x + 0.04 * k, y - 0.2 * k), (x + 0.3 * k, y - 0.02 * k), (x - 0.1 * k, y + 0.12 * k)], ACCENT)


def magnifier(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    mx = math.sin(t * 1.3) * 0.28
    my = math.sin(t * 2.6) * 0.14
    P = _pts(cx + mx * k, cy + my * k, k)
    cv.line([P(0.34, 0.34), P(0.82, 0.82)], 0.2 * k, ORANGE)
    cv.circle(*P(-0.1, -0.1), 0.62 * k, (36, 110, 190), 0.35)
    cv.ring(*P(-0.1, -0.1), 0.58 * k, 0.12 * k, TEXT)
    cv.line([P(-0.4, -0.3), P(-0.28, -0.46)], 0.07 * k, TEXT, 0.8)


def person(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    P = _pts(cx, cy + math.sin(t * 2.4) * 0.03 * s, k)
    cv.circle(*P(0, -0.42), 0.34 * k, ACCENT)
    cv.polygon([P(-0.62, 0.9), P(-0.58, 0.4), P(-0.3, 0.14), P(0.3, 0.14), P(0.58, 0.4), P(0.62, 0.9)], CYAN)
    cv.circle(*P(-0.1, -0.5), 0.045 * k, DARK)
    cv.circle(*P(0.1, -0.5), 0.045 * k, DARK)
    cv.line([P(-0.12, -0.32), P(0, -0.26), P(0.12, -0.32)], 0.04 * k, DARK)


def check(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    from .draw import soft_glow
    soft_glow(cv, cx, cy, 1.8 * k, GREEN, 0.4)
    cv.circle(cx, cy, 0.95 * k, GREEN)
    f = ease_out(clamp01((t - 0.15) / 0.6)) * 2
    path = [(cx - 0.45 * k, cy + 0.02 * k), (cx - 0.12 * k, cy + 0.36 * k), (cx + 0.5 * k, cy - 0.32 * k)]
    shown = path[: int(f) + 1]
    if int(f) < 2:
        a, b, g = path[int(f)], path[int(f) + 1], f - int(f)
        shown.append((a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g))
    if len(shown) >= 2:
        cv.line(shown, 0.18 * k, TEXT)
    ring = (t * 0.8) % 1.0
    cv.ring(cx, cy, k * (1.0 + ring * 0.5), 0.05 * k, GREEN, (1 - ring) * 0.6)


def phone(cv, cx, cy, s, p, t):
    k = _scale(s, p)
    tilt = math.sin(t * 1.6) * 0.05
    P = lambda x, y: (cx + (x * math.cos(tilt) - y * math.sin(tilt)) * k, cy + (x * math.sin(tilt) + y * math.cos(tilt)) * k)
    cv.polygon([P(-0.46, -0.92), P(0.46, -0.92), P(0.46, 0.92), P(-0.46, 0.92)], (70, 70, 120))
    cv.polygon([P(-0.4, -0.8), P(0.4, -0.8), P(0.4, 0.8), P(-0.4, 0.8)], DARK)
    for i, (w, c) in enumerate(((0.62, CYAN), (0.5, VIOLET), (0.7, ACCENT))):  # a feed scrolling by
        y = -0.6 + ((i * 0.5 + t * 0.35) % 1.5)
        if -0.7 < y < 0.7:
            cv.polygon([P(-0.32, y), P(-0.32 + w * 0.7, y), P(-0.32 + w * 0.7, y + 0.26), P(-0.32, y + 0.26)], c, 0.9)
    pulse = (t * 1.4) % 1.0
    cv.circle(*P(0.46, -0.84), 0.16 * k, PINK)
    cv.ring(*P(0.46, -0.84), (0.16 + pulse * 0.25) * k, 0.03 * k, PINK, (1 - pulse) * 0.7)


ICONS = {f.__name__: f for f in (rocket, coins, bulb, clock, heart, shield, lock, cart, house, gear, globe, star, growth,
                                  magnifier, person, check, phone)}

_KEYWORDS = [  # first match wins, so the more specific topics come first
    ("rocket", r"rocket|launch|space|orbit|startup|innovat|speed|fast|blast"),
    ("coins", r"money|cash|dollar|price|cost|budget|income|salary|wealth|rich|afford|spend|bank|debt|loan|pay|save|saving"),
    ("growth", r"grow|increas|rise|profit|invest|revenue|sales|trend|scale|climb|boost"),
    ("clock", r"time|hour|minute|daily|week|month|year|schedule|deadline|routine|morning|night"),
    ("bulb", r"idea|think|learn|tip|smart|creative|insight|lesson|understand|knowledge|brain|mind"),
    ("heart", r"love|health|care|family|friend|happy|feel|kind|heal|sleep|stress"),
    ("shield", r"safe|protect|secur|risk|insur|defen|guard|trust"),
    ("lock", r"privat|password|lock|secret|hidden|encrypt"),
    ("cart", r"shop|buy|store|grocer|market|sale|discount|cart|order"),
    ("house", r"home|house|rent|propert|mortgage|apartment|room|kitchen|bedroom"),
    ("globe", r"world|global|countr|econom|international|planet|earth|nation|trade"),
    ("gear", r"work|system|process|tool|build|fix|engine|machine|automat|technolog|method|step"),
    ("magnifier", r"search|find|look|research|discover|check|investigat|spot|detail"),
    ("person", r"people|person|team|customer|user|human|you|your|someone|everyone|leader|boss"),
    ("phone", r"phone|app|mobile|online|digital|tech|social|internet|video|scroll"),
    ("check", r"done|complete|success|correct|proof|verif|result|solve|answer|goal|win"),
    ("star", r"best|top|quality|great|favourite|favorite|amazing|powerful|famous|rating"),
]


def guess(text: str) -> str:
    """Pick the icon whose keywords best fit the text. Returns '' when nothing fits."""
    low = (text or "").lower()
    for name, pattern in _KEYWORDS:
        if re.search(pattern, low):
            return name
    return ""


def draw_icon(cv: Canvas, name: str, cx: float, cy: float, s: float, p: float, t: float) -> None:
    fn = ICONS.get(name)
    if fn and p > 0:
        fn(cv, cx, cy, s, p, t)
