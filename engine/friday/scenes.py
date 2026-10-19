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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30

# Palette: matches the app (deep navy, amber accent).
BG_TOP, BG_BOTTOM = (17, 16, 38), (9, 9, 22)
TEXT = (244, 244, 252)
MUTED = (150, 152, 196)
ACCENT = (255, 184, 61)
CYAN = (86, 204, 242)
VIOLET = (139, 124, 255)
GREEN = (52, 211, 153)
CARD = (33, 32, 64)
GRID = (48, 48, 86)

_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/Library/Fonts", "C:/Windows/Fonts"]
_FONT_FILES = {False: ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf"), True: ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf")}


# ---------------------------------------------------------------- small helpers

def clamp01(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def seg(t: float, start: float, end: float) -> float:
    """Progress 0..1 of time t between start and end."""
    return clamp01((t - start) / max(1e-6, end - start))


def ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_in_out(p: float) -> float:
    return 3 * p * p - 2 * p * p * p


def ease_back(p: float) -> float:
    """Ease out with a small overshoot, for words that pop in."""
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


@lru_cache(maxsize=64)
def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    size = max(6, int(size))
    for d in _FONT_DIRS:
        for name in _FONT_FILES[bold]:
            p = Path(d) / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def wrap(text: str, size: int, bold: bool, max_w: float) -> list[str]:
    f = font(size, bold)
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and f.getlength(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def fit_text(text: str, bold: bool, max_w: float, max_lines: int, start: int, floor: int) -> tuple[int, list[str]]:
    """Largest font size (stepping down) whose wrapped text fits max_lines and max_w."""
    size = start
    while size > floor:
        lines = wrap(text, size, bold, max_w)
        f = font(size, bold)
        if len(lines) <= max_lines and all(f.getlength(ln) <= max_w for ln in lines):
            return size, lines
        size = int(size * 0.92)
    lines = wrap(text, floor, bold, max_w)
    if len(lines) > max_lines:  # still too long: cut with an ellipsis rather than overflow
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;") + "…"
    return floor, lines


def mix(a: tuple, b: tuple, p: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * p) for i in range(3))


# ---------------------------------------------------------------- layout and canvas

@dataclass(frozen=True)
class Layout:
    w: int
    h: int
    u: float  # size unit
    x0: float
    x1: float
    y0: float  # content area, kept clear of the burned-in captions
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def make_layout(w: int, h: int) -> Layout:
    portrait = h > w
    u = min(w, h) / 1080
    if portrait:
        return Layout(w, h, u, w * 0.08, w * 0.92, h * 0.095, h * 0.645)
    return Layout(w, h, u, w * 0.07, w * 0.93, h * 0.09, h * 0.75)


class Canvas:
    """A frame being drawn. Shapes are anti-aliased by drawing them 3x larger on a mask."""

    SS = 3

    def __init__(self, base: Image.Image):
        self.img = base

    def _paste(self, color: tuple, x: int, y: int, mask: Image.Image, alpha: float) -> None:
        if alpha < 0.999:
            mask = mask.point(lambda v: int(v * alpha))
        self.img.paste(color, (x, y), mask)

    def text(self, xy: tuple[float, float], s: str, size: float, fill: tuple = TEXT, bold: bool = True,
             anchor: str = "lt", alpha: float = 1.0) -> None:
        """Draw text. anchor = horizontal (l, m, r) + vertical (t: top of the line, m: middle of the
        capitals, b: baseline). Placement uses font metrics so every word on a line shares a baseline."""
        if alpha <= 0.01 or not s:
            return
        f = font(int(size), bold)
        asc, desc = f.getmetrics()
        width = f.getlength(s)
        pad = 3
        mask = Image.new("L", (int(width) + 2 * pad + 6, asc + desc + 2 * pad), 0)
        ImageDraw.Draw(mask).text((pad, pad), s, font=f, fill=255, anchor="la")
        hx, vy = anchor[0], anchor[1]
        x = xy[0] - (0 if hx == "l" else width / 2 if hx == "m" else width) - pad
        base_in_mask = pad + asc
        baseline = xy[1] + (0.36 * int(size) if vy == "m" else 0) if vy != "t" else xy[1] + asc
        y = baseline - base_in_mask
        self._paste(fill, int(round(x)), int(round(y)), mask, alpha)

    def _shape(self, x0: float, y0: float, x1: float, y1: float, draw, fill: tuple, alpha: float) -> None:
        if alpha <= 0.01:
            return
        ss, pad = self.SS, 3
        ox, oy = int(math.floor(x0)) - pad, int(math.floor(y0)) - pad
        w, h = int(math.ceil(x1)) - ox + pad, int(math.ceil(y1)) - oy + pad
        if w < 1 or h < 1:
            return
        mask = Image.new("L", (w * ss, h * ss), 0)
        draw(ImageDraw.Draw(mask), lambda x, y: ((x - ox) * ss, (y - oy) * ss), ss)
        mask = mask.resize((w, h), Image.BOX)
        self._paste(fill, ox, oy, mask, alpha)

    def rrect(self, x0: float, y0: float, x1: float, y1: float, r: float, fill: tuple, alpha: float = 1.0) -> None:
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        self._shape(x0, y0, x1, y1, lambda d, m, ss: d.rounded_rectangle([*m(x0, y0), *m(x1, y1)], radius=r * ss, fill=255), fill, alpha)

    def circle(self, cx: float, cy: float, r: float, fill: tuple, alpha: float = 1.0) -> None:
        if r < 0.5:
            return
        self._shape(cx - r, cy - r, cx + r, cy + r, lambda d, m, ss: d.ellipse([*m(cx - r, cy - r), *m(cx + r, cy + r)], fill=255), fill, alpha)

    def line(self, pts: list[tuple[float, float]], width: float, fill: tuple, alpha: float = 1.0) -> None:
        if len(pts) < 2:
            return
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        hw = width / 2 + 1

        def draw(d, m, ss):
            mp = [m(*p) for p in pts]
            d.line(mp, fill=255, width=max(1, int(width * ss)), joint="curve")
            for x, y in (mp[0], mp[-1]):  # round caps
                d.ellipse([x - width * ss / 2, y - width * ss / 2, x + width * ss / 2, y + width * ss / 2], fill=255)

        self._shape(min(xs) - hw, min(ys) - hw, max(xs) + hw, max(ys) + hw, draw, fill, alpha)

    def polygon(self, pts: list[tuple[float, float]], fill: tuple, alpha: float = 1.0) -> None:
        if len(pts) < 3:
            return
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self._shape(min(xs), min(ys), max(xs), max(ys), lambda d, m, ss: d.polygon([m(*p) for p in pts], fill=255), fill, alpha)


@lru_cache(maxsize=8)
def _glow_mask(diameter: int) -> Image.Image:
    yy, xx = np.mgrid[0:diameter, 0:diameter].astype(np.float32)
    d = np.hypot(xx - diameter / 2, yy - diameter / 2) / (diameter / 2)
    return Image.fromarray((np.clip(1 - d, 0, 1) ** 2 * 255).astype(np.uint8), "L")


def soft_glow(cv: "Canvas", cx: float, cy: float, radius: float, color: tuple, alpha: float) -> None:
    d = max(8, int(radius * 2) // 8 * 8)  # bucketed so the cache stays small
    cv._paste(color, int(cx - d / 2), int(cy - d / 2), _glow_mask(d), alpha)


class Background:
    """Navy gradient with two slow-moving soft glows. Built once per size."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        col = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        top, bot = np.array(BG_TOP, np.float32), np.array(BG_BOTTOM, np.float32)
        arr = (top + (bot - top) * col) * np.ones((1, w, 1), np.float32)
        self.base = Image.fromarray(arr.astype(np.uint8), "RGB")
        size = int(min(w, h) * 1.1)
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        d = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
        self.glow = Image.fromarray((np.clip(1 - d, 0, 1) ** 2 * 70).astype(np.uint8), "L")
        self.size = size

    def frame(self, t: float) -> Image.Image:
        img = self.base.copy()
        for i, color in enumerate((VIOLET, CYAN)):
            ang = t * 0.18 + i * math.pi
            cx = self.w * (0.5 + 0.38 * math.cos(ang * 0.9 + i))
            cy = self.h * (0.5 + 0.38 * math.sin(ang + i * 2))
            img.paste(color, (int(cx - self.size / 2), int(cy - self.size / 2)), self.glow)
        return img


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


SCENES = {
    "title": scene_title,
    "statement": scene_statement,
    "big_number": scene_big_number,
    "bars": scene_bars,
    "line": scene_line,
    "timeline": scene_timeline,
    "points": scene_points,
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
    fade = min(1.0, t / 0.18, max(0.0, (dur - t) / 0.18))  # quick fade at both ends
    return layer if fade >= 0.999 else Image.blend(bg, layer, max(0.0, fade))


def render_frames(kind: str, data: dict, dur: float, t0: float, w: int, h: int) -> Iterator[bytes]:
    """Raw RGB frames for one scene lasting `dur` seconds, starting at video time t0."""
    for i in range(max(1, round(dur * FPS))):
        yield render_frame(kind, data, i / FPS, dur, t0, w, h).tobytes()
