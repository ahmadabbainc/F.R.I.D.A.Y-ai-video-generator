"""Drawing basics shared by the animated scenes and icons: palette, easing, fonts, an anti-aliased canvas and the background."""

from __future__ import annotations

import math
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

    def ring(self, cx: float, cy: float, r: float, width: float, fill: tuple, alpha: float = 1.0) -> None:
        if r < 1 or width < 0.5:
            return
        o = r + width / 2

        def draw(d, m, ss):
            d.ellipse([*m(cx - o, cy - o), *m(cx + o, cy + o)], fill=255)
            i = r - width / 2
            if i > 0:
                d.ellipse([*m(cx - i, cy - i), *m(cx + i, cy + i)], fill=0)

        self._shape(cx - o, cy - o, cx + o, cy + o, draw, fill, alpha)

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
        rng = np.random.RandomState(7)
        n = 34
        self.motes = [  # (x, y, radius, rise speed, alpha, colour): near ones are bigger and faster
            (rng.rand(), rng.rand(), 2 + 7 * d, 0.012 + 0.05 * d, 0.12 + 0.3 * d, (TEXT, CYAN, VIOLET)[i % 3])
            for i, d in enumerate(rng.rand(n) ** 2)
        ]

    def frame(self, t: float) -> Image.Image:
        img = self.base.copy()
        for i, color in enumerate((VIOLET, CYAN)):
            ang = t * 0.18 + i * math.pi
            cx = self.w * (0.5 + 0.38 * math.cos(ang * 0.9 + i))
            cy = self.h * (0.5 + 0.38 * math.sin(ang + i * 2))
            img.paste(color, (int(cx - self.size / 2), int(cy - self.size / 2)), self.glow)
        cv = Canvas(img)
        u = min(self.w, self.h) / 1080
        for x, y, r, speed, a, color in self.motes:  # drifting dust: gives constant gentle motion
            px = (x + 0.02 * math.sin(t * 0.5 + y * 9)) % 1.0
            py = (y - speed * t) % 1.0
            cv.circle(px * self.w, py * self.h, r * u, color, a)
        return img


