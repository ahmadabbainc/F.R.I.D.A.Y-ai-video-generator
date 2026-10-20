"""Animated explainer scenes, drawn entirely by code (Pillow + numpy).

Each scene type is a function that draws one frame for a time `t` (seconds since
the scene began). render_frames() turns a scene into raw RGB frames that ffmpeg
encodes. Nothing here touches the network, so it is free and always available.

All sizes are multiplied by a unit `u` (1.0 at 1080 px on the short side), so the
same scenes work at any resolution, including the tiny sizes used in tests.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from PIL import Image

from . import icons

from .draw import (
    ACCENT, BG_BOTTOM, BG_TOP, CARD, CYAN, FPS, GREEN, GRID, MUTED, TEXT, VIOLET,
    Background, Canvas, Layout, clamp01, ease_back, ease_in_out, ease_out, fit_text, font, make_layout,
    mix, seg, soft_glow, wrap,
)

# ---------------------------------------------------------------- shared pieces

def heading(cv: Canvas, lay: Layout, title: str, t: float) -> float:
    """Chart title with a growing accent bar. Returns the y where content may start."""
    u = lay.u
    size, lines = fit_text(title, True, lay.width, 2, int(64 * u), int(40 * u))
    p = ease_out(seg(t, 0.0, 0.5))
    y = lay.y0
    cv.rrect(lay.x0, y + 4 * u, lay.x0 + 90 * u * p, y + 14 * u, 5 * u, ACCENT)
    y += 34 * u
    for ln in lines:
        cv.text((lay.x0, y + (1 - p) * 24 * u), ln, size, TEXT, True, "lt", p)
        y += size * 1.28
    return y + 30 * u


def number_text(value: float, decimals: int, prefix: str = "", suffix: str = "") -> str:
    body = f"{value:,.{decimals}f}"
    return f"{prefix}{body}{suffix}"


def decimals_of(value: float) -> int:
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return min(2, len(s.split(".")[1])) if "." in s else 0


def layout_words(words: list[str], size: int, bold: bool, max_w: float) -> list[list[tuple[str, float, float]]]:
    """Lines of (word, x offset, width), left aligned. Used for word-by-word reveals."""
    f = font(size, bold)
    space = f.getlength(" ")
    lines: list[list[tuple[str, float, float]]] = [[]]
    x = 0.0
    for w in words:
        wl = f.getlength(w)
        if lines[-1] and x + wl > max_w:
            lines.append([])
            x = 0.0
        lines[-1].append((w, x, wl))
        x += wl + space
    return lines


def pop_words(cv: Canvas, lay: Layout, text: str, t: float, dur: float, top: float, bottom: float,
              start_size: int, highlight: set[str], center: bool = True, color: tuple = TEXT) -> float:
    """Draw text that pops in word by word, vertically centred between top and bottom."""
    u = lay.u
    words = text.split()
    size = start_size
    while True:
        lines = layout_words(words, size, True, lay.width)
        if (len(lines) * size * 1.22 <= bottom - top) or size <= 34 * u:
            break
        size = int(size * 0.92)
    lh = size * 1.22
    total_h = len(lines) * lh
    y = top + max(0, (bottom - top - total_h) / 2)
    n = len(words)
    window = min(dur * 0.55, 0.12 * n + 0.2)
    gap = window / max(1, n)
    idx = 0
    for line in lines:
        line_w = line[-1][1] + line[-1][2]
        ox = lay.x0 + ((lay.width - line_w) / 2 if center else 0)
        for word, x, _w in line:
            p = seg(t, 0.15 + idx * gap, 0.15 + idx * gap + 0.4)
            clean = word.strip(".,;:!?\"'()").lower()
            col = ACCENT if clean in highlight else color
            cv.text((ox + x, y + (1 - ease_back(p)) * 40 * u), word, size, col, True, "lt", ease_out(p))
            idx += 1
        y += lh
    return y


def auto_highlight(text: str) -> set[str]:
    words = [w.strip(".,;:!?\"'()") for w in text.split()]
    picks = {w.lower() for w in words if any(c.isdigit() for c in w)}
    picks |= {w.lower() for i, w in enumerate(words) if i and w[:1].isupper() and len(w) > 2}
    if not picks:
        long = sorted((w for w in words if len(w) > 5), key=len, reverse=True)[:2]
        picks = {w.lower() for w in long}
    return picks


# ---------------------------------------------------------------- scene types

def scene_title(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    title = data.get("title", "")
    sub = data.get("subtitle", "")
    sub_h = 120 * u if sub else 0
    end = pop_words(cv, lay, title, t, dur, lay.y0, lay.y1 - sub_h, int(120 * u), set())
    bar = ease_out(seg(t, 0.5, 1.1))
    cv.rrect(lay.cx - 80 * u * bar, end + 18 * u, lay.cx + 80 * u * bar, end + 30 * u, 6 * u, ACCENT)
    if sub:
        p = ease_out(seg(t, 0.9, 1.5))
        size, lines = fit_text(sub, False, lay.width, 2, int(46 * u), int(30 * u))
        y = end + 56 * u + (1 - p) * 20 * u
        for ln in lines:
            cv.text((lay.cx, y), ln, size, MUTED, False, "mt", p)
            y += size * 1.3


def scene_statement(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    text = data.get("text", "")
    hl = {h.lower() for h in data.get("highlight", [])} or auto_highlight(text)
    pop_words(cv, lay, text, t, dur, lay.y0, lay.y1, int(104 * lay.u), hl)


def scene_big_number(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    value = float(data["value"])
    dec = decimals_of(value)
    prefix, suffix = data.get("prefix", ""), data.get("suffix", "")
    final = number_text(value, dec, prefix, suffix)
    size = int(230 * u)
    while font(size, True).getlength(final) > lay.width and size > 40 * u:
        size = int(size * 0.93)
    count = ease_out(seg(t, 0.25, min(dur * 0.75, 2.4)))
    shown = number_text(value * count, dec, prefix, suffix)
    cy = (lay.y0 + lay.y1) / 2
    glow = 0.10 + 0.05 * math.sin(t * 2.2)
    soft_glow(cv, lay.cx, cy, min(lay.width, lay.height) * 0.62, ACCENT, glow * 2.2)
    fade = ease_out(seg(t, 0.0, 0.4))
    label = data.get("label", "")
    lsize, lines = fit_text(label, False, lay.width, 3, int(52 * u), int(30 * u))
    ly = cy - size * 0.62 - len(lines) * lsize * 1.3
    for ln in lines:
        cv.text((lay.cx, ly + (1 - fade) * 20 * u), ln, lsize, MUTED, False, "mt", fade)
        ly += lsize * 1.3
    cv.text((lay.cx, cy), shown, size, ACCENT, True, "mm", fade)
    bar = ease_out(seg(t, 0.4, 1.1))
    by = cy + size * 0.62
    cv.rrect(lay.cx - 90 * u * bar, by, lay.cx + 90 * u * bar, by + 12 * u, 6 * u, TEXT, 0.9)
    cap = data.get("caption", "")
    if cap:
        p = ease_out(seg(t, 1.0, 1.6))
        csize, clines = fit_text(cap, False, lay.width, 2, int(40 * u), int(28 * u))
        y = by + 44 * u
        for ln in clines:
            cv.text((lay.cx, y), ln, csize, MUTED, False, "mt", p)
            y += csize * 1.3


def scene_bars(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t)
    items = data["items"]
    prefix, suffix = data.get("prefix", ""), data.get("suffix", "")
    n = len(items)
    row = min(300 * u, (lay.y1 - top) / n)
    top += max(0.0, (lay.y1 - top - row * n) / 2)
    vmax = max(i["value"] for i in items) or 1
    peak = max(range(n), key=lambda i: items[i]["value"])
    dec = max(decimals_of(i["value"]) for i in items)
    value_w = max(font(int(48 * u), True).getlength(number_text(i["value"], dec, prefix, suffix)) for i in items)
    bar_max = lay.width - value_w - 24 * u
    for i, it in enumerate(items):
        p = ease_out(seg(t, 0.35 + i * 0.18, 1.35 + i * 0.18))
        y = top + i * row
        lab = it["label"]
        cv.text((lay.x0, y), lab, 44 * u, MUTED, False, "lt", clamp01(p * 2))
        by = y + 66 * u
        bh = min(68 * u, row * 0.34)
        color = ACCENT if i == peak else CYAN
        cv.rrect(lay.x0, by, lay.x0 + bar_max, by + bh, bh / 2, CARD)
        length = max(bh, bar_max * (it["value"] / vmax) * p)
        if p > 0.01:
            cv.rrect(lay.x0, by, lay.x0 + length, by + bh, bh / 2, color)
        cv.text((lay.x0 + length + 18 * u, by + bh / 2), number_text(it["value"] * p, dec, prefix, suffix), 48 * u,
                TEXT if i != peak else ACCENT, True, "lm", clamp01(p * 3))


def scene_line(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t)
    pts = data["points"]
    prefix, suffix = data.get("prefix", ""), data.get("suffix", "")
    n = len(pts)
    vals = [p["value"] for p in pts]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.2 or max(1.0, abs(hi) * 0.2)
    lo, hi = lo - pad, hi + pad
    px0, px1 = lay.x0 + 30 * u, lay.x1 - 30 * u
    py0, py1 = top + 50 * u, lay.y1 - 60 * u
    for g in range(4):
        gy = py0 + (py1 - py0) * g / 3
        cv.line([(lay.x0, gy), (lay.x1, gy)], max(1.5, 2 * u), GRID, 0.7)

    def xy(i: int, v: float) -> tuple[float, float]:
        return px0 + (px1 - px0) * i / (n - 1), py1 - (py1 - py0) * (v - lo) / (hi - lo)

    coords = [xy(i, v) for i, v in enumerate(vals)]
    draw = ease_in_out(seg(t, 0.3, min(dur * 0.8, 2.8)))
    reach_total = draw * (n - 1 + 0.5)  # the extra half step lets the last point finish popping in
    reach = min(reach_total, n - 1)
    path = list(coords[: int(reach) + 1])
    if int(reach) < n - 1:
        a, b, f = coords[int(reach)], coords[int(reach) + 1], reach - int(reach)
        path.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    if len(path) >= 2:
        cv.polygon(path + [(path[-1][0], py1), (path[0][0], py1)], CYAN, 0.13)
        cv.line(path, max(5, 8 * u), CYAN)
    peak = max(range(n), key=lambda i: vals[i])
    dec = max(decimals_of(v) for v in vals)
    for i, (x, y) in enumerate(coords):
        shown = 1.0 if i == 0 and t > 0.3 else clamp01((reach_total - i) / 0.5)
        if shown <= 0:
            continue
        cv.circle(x, y, 12 * u * ease_back(clamp01(shown)), ACCENT if i == peak else TEXT)
        if n <= 6 or i in (0, n - 1, peak):
            label = number_text(vals[i], dec, prefix, suffix)
            lw = font(int(36 * u), True).getlength(label)
            cx = min(max(x, lay.x0 + lw / 2 + 14 * u), lay.x1 - lw / 2 - 14 * u)  # keep labels on screen
            fa = clamp01(shown * 1.5)
            cv.rrect(cx - lw / 2 - 14 * u, y - 100 * u, cx + lw / 2 + 14 * u, y - 40 * u, 16 * u, BG_BOTTOM, 0.85 * fa)
            cv.text((cx, y - 54 * u), label, 36 * u, ACCENT if i == peak else TEXT, True, "mb", fa)
        if n <= 6 or i in (0, n - 1):
            cv.text((x, py1 + 22 * u), pts[i]["label"], 34 * u, MUTED, False, "mt", clamp01(shown * 1.5))


def scene_timeline(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t)
    events = data["events"]
    n = len(events)
    row = min(300 * u, (lay.y1 - top) / n)
    top += max(0.0, (lay.y1 - top - row * n) / 2)
    when_w = lay.width * 0.27
    mx = lay.x0 + when_w + 36 * u
    grow = ease_out(seg(t, 0.2, 1.4))
    y_first, y_last = top + row * 0.28, top + row * (n - 0.72)
    cv.line([(mx, y_first), (mx, y_first + (y_last - y_first) * grow)], max(4, 6 * u), GRID)
    for i, ev in enumerate(events):
        p = ease_out(seg(t, 0.5 + i * 0.35, 1.0 + i * 0.35))
        cy = top + row * (i + 0.28)
        cv.text((lay.x0 + when_w, cy), ev["when"], 44 * u, ACCENT, True, "rm", p)
        cv.circle(mx, cy, 17 * u * ease_back(p), ACCENT if i == n - 1 else CYAN)
        size, lines = fit_text(ev["what"], False, lay.x1 - mx - 56 * u, 3, int(46 * u), int(28 * u))
        ty = cy - (len(lines) * size * 1.25) / 2
        for ln in lines:
            cv.text((mx + 40 * u + (1 - p) * 30 * u, ty), ln, size, TEXT, False, "lt", p)
            ty += size * 1.25


def scene_points(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t)
    items = data["items"]
    n = len(items)
    gap = 22 * u
    row = min(270 * u, (lay.y1 - top) / n)
    top += max(0.0, (lay.y1 - top - row * n) / 2)
    for i, text in enumerate(items):
        p = ease_out(seg(t, 0.4 + i * 0.4, 0.95 + i * 0.4))
        y0 = top + i * row
        y1 = y0 + row - gap
        off = (1 - p) * 70 * u
        cv.rrect(lay.x0 + off, y0, lay.x1 + off, y1, 26 * u, CARD, p)
        r = min(38 * u, (y1 - y0) * 0.3)
        cv.circle(lay.x0 + off + 34 * u + r, (y0 + y1) / 2, r, ACCENT, p)
        cv.text((lay.x0 + off + 34 * u + r, (y0 + y1) / 2), str(i + 1), r * 1.2, (30, 24, 8), True, "mm", p)
        tx = lay.x0 + off + 34 * u + r * 2 + 28 * u
        size, lines = fit_text(text, False, lay.x1 + off - tx - 24 * u, 3, int(44 * u), int(26 * u))
        ty = (y0 + y1) / 2 - len(lines) * size * 1.25 / 2
        for ln in lines:
            cv.text((tx, ty), ln, size, TEXT, False, "lt", p)
            ty += size * 1.25


def scene_statement(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    text = data.get("text", "")
    hl = {h.lower() for h in data.get("highlight", [])} or auto_highlight(text)
    top = lay.y0
    name = data.get("icon", "")
    if name in icons.ICONS:
        size = min(lay.width * 0.2, lay.height * 0.16)
        icons.draw_icon(cv, name, lay.cx, lay.y0 + size * 1.15, size, seg(t, 0.0, 0.7), t)
        top = lay.y0 + size * 2.5
    pop_words(cv, lay, text, t, dur, top, lay.y1, int(100 * lay.u), hl)


def scene_icon(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    """One big animated icon with rings pulsing out of it and a caption popping in below."""
    u = lay.u
    wide = lay.w > lay.h
    size = min(lay.width * 0.3, lay.height * (0.19 if wide else 0.27))
    cy = lay.y0 + lay.height * (0.3 if wide else 0.36)
    soft_glow(cv, lay.cx, cy, size * 2.4, VIOLET, 0.35)
    fade = ease_out(seg(t, 0.0, 0.5))
    for i in range(3):
        f = (t * 0.4 + i / 3) % 1.0
        cv.ring(lay.cx, cy, size * (1.15 + f * 1.1), max(3, 5 * u), CYAN, (1 - f) * 0.45 * fade)
    icons.draw_icon(cv, data.get("icon", "star"), lay.cx, cy, size, seg(t, 0.05, 0.8), t)
    end = pop_words(cv, lay, data.get("label", ""), t - 0.4, dur, cy + size * (1.4 if wide else 1.5), lay.y1 - 120 * u, int(86 * u), auto_highlight(data.get("label", "")))
    cap = data.get("caption", "")
    if cap:
        p = ease_out(seg(t, 1.4, 2.0))
        csize, lines = fit_text(cap, False, lay.width, 2, int(40 * u), int(28 * u))
        y = end + 14 * u + (1 - p) * 20 * u
        for ln in lines:
            cv.text((lay.cx, y), ln, csize, MUTED, False, "mt", p)
            y += csize * 1.3


def _pulse_along(cv: Canvas, a: tuple[float, float], b: tuple[float, float], t: float, color: tuple, u: float, alpha: float = 1.0) -> None:
    f = (t * 0.7) % 1.0
    cv.circle(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, 9 * u, color, alpha)


def scene_flow(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    """Steps connected by lines, with pulses of light travelling from step to step."""
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t)
    steps = data["steps"]
    n = len(steps)
    portrait = lay.h > lay.w
    nodes = []
    row = 0.0
    if portrait:
        row = min(280 * u, (lay.y1 - top) / n)
        top += max(0.0, (lay.y1 - top - row * n) / 2)
        nodes = [(lay.x0 + 125 * u, top + row * (i + 0.5)) for i in range(n)]
    else:
        col = lay.width / n
        nodes = [(lay.x0 + col * (i + 0.5), top + (lay.y1 - top) * 0.36) for i in range(n)]
    r = min((112 if portrait else 120) * u, (row * 0.4) if portrait else 120 * u)
    for i in range(n - 1):  # connectors first, so the nodes sit on top of them
        a, b = nodes[i], nodes[i + 1]
        g = ease_out(seg(t, 0.5 + i * 0.5, 1.1 + i * 0.5))
        if g > 0:
            end = (a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g)
            cv.line([a, end], max(4, 7 * u), GRID)
            if g >= 1:
                _pulse_along(cv, a, b, t - i * 0.25, ACCENT, u)
    for i, st in enumerate(steps):
        p = seg(t, 0.35 + i * 0.5, 0.95 + i * 0.5)
        x, y = nodes[i]
        k = ease_back(p)
        cv.circle(x, y, r * k, CARD)
        cv.ring(x, y, r * k, max(3, 5 * u), ACCENT if i == n - 1 else CYAN, clamp01(p * 2))
        icons.draw_icon(cv, st["icon"], x, y, r * 0.62, p, t - i * 0.3)
        size, lines = fit_text(st["label"], True, (lay.x1 - x - r - 40 * u) if portrait else lay.width / n - 20 * u, 3, int(54 * u), int(30 * u))
        if portrait:
            ty = y - len(lines) * size * 1.2 / 2
            for ln in lines:
                cv.text((x + r + 36 * u + (1 - ease_out(p)) * 40 * u, ty), ln, size, TEXT, True, "lt", ease_out(p))
                ty += size * 1.2
        else:
            ty = y + r + 24 * u
            for ln in lines:
                cv.text((x, ty), ln, size, TEXT, True, "mt", ease_out(p))
                ty += size * 1.2


def scene_compare(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    """Two sides head to head, with a pulsing VS badge between them."""
    u = lay.u
    top = heading(cv, lay, data.get("title", ""), t) if data.get("title") else lay.y0
    portrait = lay.h > lay.w
    gap = 70 * u
    if portrait:
        ch = (lay.y1 - top - gap) / 2
        boxes = [(lay.x0, top, lay.x1, top + ch), (lay.x0, top + ch + gap, lay.x1, top + 2 * ch + gap)]
    else:
        cw = (lay.width - gap) / 2
        boxes = [(lay.x0, top, lay.x0 + cw, lay.y1), (lay.x0 + cw + gap, top, lay.x1, lay.y1)]
    for i, side in enumerate((data["left"], data["right"])):
        p = seg(t, 0.3 + i * 0.45, 0.95 + i * 0.45)
        x0, y0, x1, y1 = boxes[i]
        off = (1 - ease_out(p)) * (-1 if i == 0 else 1) * 90 * u * (0 if portrait else 1)
        offy = (1 - ease_out(p)) * (-1 if i == 0 else 1) * 90 * u * (1 if portrait else 0)
        x0, x1, y0, y1 = x0 + off, x1 + off, y0 + offy, y1 + offy
        col = CYAN if i == 0 else ACCENT
        cv.rrect(x0, y0, x1, y1, 30 * u, CARD, ease_out(p))
        cv.rrect(x0, y0, x0 + 12 * u, y1, 6 * u, col, ease_out(p)) if portrait else cv.rrect(x0, y0, x1, y0 + 12 * u, 6 * u, col, ease_out(p))
        isz = min(100 * u, (y1 - y0) * 0.3)
        icons.draw_icon(cv, side["icon"], x0 + 60 * u + isz, (y0 + y1) / 2 if portrait and not side["points"] else y0 + 40 * u + isz, isz * 0.9, p, t)
        tx = x0 + 60 * u + isz * 2 + 20 * u if portrait else x0 + 40 * u
        ty = y0 + 40 * u if portrait else y0 + 60 * u + isz * 2
        cv.text((tx, ty), side["label"], 60 * u, col, True, "lt", ease_out(p))
        ty += 90 * u
        for pt in side["points"]:
            size, lines = fit_text(pt, False, x1 - tx - 40 * u, 2, int(42 * u), int(26 * u))
            cv.text((tx, ty), "•", size, col, True, "lt", ease_out(p))
            for ln in lines:
                cv.text((tx + 34 * u, ty), ln, size, TEXT, False, "lt", ease_out(p))
                ty += size * 1.25
            ty += 14 * u
    vp = ease_back(seg(t, 1.0, 1.5))
    vx, vy = (lay.cx, boxes[0][3] + gap / 2) if portrait else (boxes[0][2] + gap / 2, (top + lay.y1) / 2)
    pulse = 1 + 0.07 * math.sin(t * 5)
    cv.circle(vx, vy, 56 * u * vp * pulse, ACCENT)
    cv.text((vx, vy), "VS", 44 * u * vp, (30, 24, 8), True, "mm", clamp01(vp))


def scene_orbit(cv: Canvas, lay: Layout, data: dict, t: float, dur: float) -> None:
    """A central idea with related ideas orbiting around it on lines of light."""
    u = lay.u
    cx, cy = lay.cx, (lay.y0 + lay.y1) / 2
    items = data["items"]
    n = len(items)
    rx, ry = lay.width * 0.36, min(lay.height * 0.38, lay.width * 0.52)
    cp = seg(t, 0.0, 0.7)
    soft_glow(cv, cx, cy, 340 * u, VIOLET, 0.35 * ease_out(cp))
    positions = []
    for i in range(n):
        a = -math.pi / 2 + i / n * math.tau + t * 0.28
        positions.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry))
    for i, (x, y) in enumerate(positions):
        g = ease_out(seg(t, 0.5 + i * 0.25, 1.1 + i * 0.25))
        cv.line([(cx, cy), (cx + (x - cx) * g, cy + (y - cy) * g)], max(3, 5 * u), GRID, 0.9)
        if g >= 1:
            _pulse_along(cv, (cx, cy), (x, y), t + i * 0.37, (CYAN, ACCENT, VIOLET, GREEN)[i % 4], u, 0.9)
    r = 150 * u
    cv.circle(cx, cy, r * ease_back(cp), CARD)
    cv.ring(cx, cy, r * ease_back(cp), max(4, 6 * u), ACCENT, cp)
    icons.draw_icon(cv, data["icon"], cx, cy, r * 0.6, cp, t)
    for i, (x, y) in enumerate(positions):
        p = seg(t, 0.55 + i * 0.25, 1.1 + i * 0.25)
        size = int(46 * u)
        wd = font(size, True).getlength(items[i]) + 56 * u
        x = min(max(x, lay.x0 + wd / 2), lay.x1 - wd / 2)
        k = ease_back(p)
        col = (CYAN, ACCENT, VIOLET, GREEN)[i % 4]
        cv.rrect(x - wd / 2 * k, y - 42 * u * k, x + wd / 2 * k, y + 42 * u * k, 42 * u * k, col, clamp01(p * 2))
        cv.text((x, y), items[i], size * k, (24, 22, 52), True, "mm", clamp01(p * 2))
    lw = font(int(56 * u), True).getlength(data["label"])  # the centre label goes on top, so a passing chip never hides it
    ly = cy + r + 30 * u
    cv.rrect(cx - lw / 2 - 22 * u, ly - 8 * u, cx + lw / 2 + 22 * u, ly + 74 * u, 30 * u, BG_BOTTOM, 0.9 * ease_out(cp))
    cv.text((cx, ly), data["label"], 56 * u, TEXT, True, "mt", ease_out(cp))


SCENES = {
    "title": scene_title,
    "statement": scene_statement,
    "icon": scene_icon,
    "big_number": scene_big_number,
    "bars": scene_bars,
    "line": scene_line,
    "timeline": scene_timeline,
    "points": scene_points,
    "flow": scene_flow,
    "compare": scene_compare,
    "orbit": scene_orbit,
}


# ---------------------------------------------------------------- frames

_BG: dict[tuple[int, int], Background] = {}


def background(w: int, h: int) -> Background:
    if (w, h) not in _BG:
        _BG[(w, h)] = Background(w, h)
    return _BG[(w, h)]


def render_frame(kind: str, data: dict, t: float, dur: float, t0: float, w: int, h: int) -> Image.Image:
    bg = background(w, h).frame(t0 + t)
    lay = make_layout(w, h)
    layer = bg.copy()
    SCENES.get(kind, scene_statement)(Canvas(layer), lay, data, t, dur)
    zoom = 1.0 + 0.05 * clamp01(t / max(dur, 0.1))  # slow push-in keeps every scene alive
    if zoom > 1.001:
        cw, ch = w / zoom, h / zoom
        left, top = (w - cw) / 2, (h - ch) / 2
        layer = layer.resize((w, h), Image.BILINEAR, box=(left, top, left + cw, top + ch))
    fade = min(1.0, t / 0.18, max(0.0, (dur - t) / 0.18))  # quick fade at both ends
    out = layer if fade >= 0.999 else Image.blend(bg, layer, max(0.0, fade))
    if t0 > 0.01 and t < 0.55:  # a swipe of colour carries the eye from the previous scene
        p = ease_in_out(t / 0.55)
        skew = h * 0.22
        for i, (col, width) in enumerate(((ACCENT, 0.34), (CYAN, 0.16))):
            x = -width * w - skew + (w + width * w + skew * 2 + w * 0.3) * clamp01(p - i * 0.08)
            bw = width * w
            Canvas(out).polygon([(x, 0), (x + bw, 0), (x + bw - skew, h), (x - skew, h)], col, 0.92 * (1 - 0.5 * p))
    return out


def render_frames(kind: str, data: dict, dur: float, t0: float, w: int, h: int) -> Iterator[bytes]:
    """Raw RGB frames for one scene lasting `dur` seconds, starting at video time t0."""
    for i in range(max(1, round(dur * FPS))):
        yield render_frame(kind, data, i / FPS, dur, t0, w, h).tobytes()
