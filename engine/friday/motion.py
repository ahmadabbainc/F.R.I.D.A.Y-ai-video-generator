"""Motion videos: bold kinetic typography, 3D and UI-style scenes, drawn in a headless browser.

The AI (or a template, with no key) writes a storyboard of scene types. Each scene is
checked and cleaned here, so a bad answer can never break the video. The browser page
in motion_assets draws any frame from a time value; this module feeds it the timeline
and pipes the frames into ffmpeg.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import script
from .config import Settings

ASSETS = Path(__file__).parent / "motion_assets"
TYPES = ("kinetic", "burst", "number", "list", "pattern", "ring", "cube", "phone", "route", "world")
FACT_TYPES = {"number"}


class MotionError(RuntimeError):
    pass


@dataclass
class Beat:
    narration: str
    type: str
    data: dict = field(default_factory=dict)
    theme: int = 0
    dur: float = 0.0


def _s(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n].strip()


def _items(v, n: int, each: int = 40) -> list[str]:
    return [t for t in (_s(x, each) for x in (v if isinstance(v, list) else [])) if t][:n]


def _lines(narration: str) -> list[str]:
    """Split a sentence into 2-4 short display lines."""
    words = narration.replace("\n", " ").split()[:12]
    n = 2 if len(words) <= 6 else 3 if len(words) <= 9 else 4
    size = -(-len(words) // n)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [narration[:30]]


def sanitize_beat(raw: dict, index: int = 0) -> Beat | None:
    if not isinstance(raw, dict):
        return None
    narration = _s(raw.get("narration"), 400)
    if not narration:
        return None
    kind = raw.get("type") if raw.get("type") in TYPES else "kinetic"
    d = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    theme = raw.get("theme") if isinstance(raw.get("theme"), int) else index
    if kind == "kinetic":
        lines = [t for t in (_s(x, 24) for x in d.get("lines", []) if isinstance(x, (str, int))) if t][:4] if isinstance(d.get("lines"), list) else []
        data = {"lines": lines or _lines(narration), "sub": _s(d.get("sub"), 50)}
        if isinstance(d.get("accent"), int):
            data["accent"] = d["accent"]
    elif kind in ("burst", "pattern", "ring"):
        text = _s(d.get("text"), 28) or _s(narration, 28)
        data = {"text": text, "sub": _s(d.get("sub"), 50)}
    elif kind in ("cube", "world"):
        data = {"text": _s(d.get("text"), 30) or _s(narration, 30)}
    elif kind == "number":
        try:
            value = float(d.get("value"))
        except (TypeError, ValueError):
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"value": int(value) if value == int(value) else round(value, 1), "prefix": _s(d.get("prefix"), 3),
                "suffix": _s(d.get("suffix"), 6), "label": _s(d.get("label"), 40)}
    elif kind == "list":
        items = _items(d.get("items"), 5)
        if len(items) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 24) or "Key points", "items": items}
    elif kind == "phone":
        items = _items(d.get("items"), 4, 28)
        if len(items) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 22) or "App", "items": items, "text": _s(d.get("text"), 26)}
    else:  # route
        points = _items(d.get("points"), 4, 18)
        if len(points) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 26), "points": points}
    return Beat(narration, kind, data, theme)


def parse_storyboard(content: str) -> list[Beat]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    beats = [b for i, s in enumerate(data["scenes"]) if (b := sanitize_beat(s, i))]
    if not beats:
        raise ValueError("empty storyboard")
    return beats


SYSTEM = """You write short motion-graphics videos: bold animated typography, 3D shapes and app-style scenes. Every scene has narration (spoken aloud) and a visual drawn by code, so the visual must reflect what the narration says.
Reply with JSON only: {"scenes":[{"narration":"...","type":"...","theme":0,"data":{...}}]}
Scene types and their data (all text is SHORT, shown in big capital letters):
- kinetic: {"lines":["2-4 words max","per line","up to 4 lines"],"accent":1,"sub":"optional small italic line"}. The workhorse: the key phrase as punchy stacked words. "accent" is the index of the line to highlight.
- burst: {"text":"TWO WORDS","sub":"optional"}. Loud sticker-style word over a sunburst. Hooks and big reveals.
- number: {"value":85,"prefix":"","suffix":"%","label":"what it measures","fill":0.85}. One striking figure counting up. fill is 0 to 1.
- list: {"title":"3 words","items":["short","short","short"]} 3 to 5 items with check marks.
- pattern: {"text":"SHORT TITLE","sub":"optional"}. Colourful animated tile pattern with a title card.
- ring: {"text":"SHORT TITLE","sub":"optional"}. Glowing 3D particle ring on dark. Tech, space, energy, the future.
- cube: {"text":"SHORT TITLE"}. A turning 3D shape. Ideas, products, building blocks.
- phone: {"title":"App name","items":["feature","feature","feature"],"text":"optional caption"}. A phone showing a few cards. Apps, software, services.
- route: {"title":"optional","points":["Start","Middle","End"]} 2 to 4 places. Journeys, steps in order, supply chains.
- world: {"text":"SHORT TITLE"}. A small isometric 3D city growing while the camera orbits. Cities, growth, economies, systems.
"theme" is 0 to 7, a colour palette: 0 cream, 1 midnight, 2 yellow, 3 blue, 4 black and orange, 5 ice, 6 forest, 7 red. Change it between scenes.
Rules:
- Open with a burst or kinetic hook. Close with a kinetic scene that lands the point.
- Mostly kinetic, with other types where they genuinely fit. Never the same type twice in a row.
- Use numbers and statistics ONLY when you are confident they are real. Never invent figures.
- Plain spoken language, no stage directions, no emojis."""


def llm_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> list[Beat]:
    n = script.scene_count(seconds)
    words = int(seconds * script.WORDS_PER_SECOND)
    user = f"Title: {title}\nTopic: {topic}\nWrite exactly {n} scenes, about {words} words of narration in total."
    if style_hint:
        user += f"\nStyle notes: {style_hint}"
    return parse_storyboard(script.chat(settings, SYSTEM, user))


_ROTATION = ("burst", "kinetic", "cube", "kinetic", "ring", "kinetic", "world", "kinetic", "pattern", "kinetic")


def demo_storyboard(title: str, topic: str, seconds: int) -> list[Beat]:
    """No key: the template sentences become stacked-type scenes, with other looks mixed in."""
    lines = [s.narration for s in script.demo_script(title, topic, seconds)]
    beats = []
    for i, line in enumerate(lines):
        kind = _ROTATION[i % len(_ROTATION)]
        data: dict = {}
        if kind in ("burst", "cube", "ring", "world", "pattern"):
            data = {"text": " ".join(line.split()[:3])}
        beats.append(sanitize_beat({"narration": line, "type": kind, "data": data}, i) or Beat(line, "kinetic", {"lines": _lines(line)}, i))
    return beats


def make_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> tuple[list[Beat], list[str]]:
    warnings: list[str] = []
    if settings.live_script:
        try:
            beats = llm_storyboard(title, topic, seconds, settings, style_hint)
            if any(b.type in FACT_TYPES for b in beats):
                warnings.append("Numbers in motion videos are written by the AI. Check them before you publish.")
            return beats, warnings
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", "")
            warnings.append(f"Script writer unavailable, used a template instead ({exc.__class__.__name__} {code}).".replace(" )", ")"))
    else:
        warnings.append("No script key set, used a template script. Add FRIDAY_LLM_API_KEY for real scripts.")
    return demo_storyboard(title, topic, seconds), warnings


# ---------- browser driver ----------

def find_chromium() -> str | None:
    env = os.environ.get("FRIDAY_CHROMIUM")
    if env and Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    for pattern in ("chromium-*/chrome-linux*/chrome", "chromium/chrome-linux*/chrome", "chromium"):
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                return str(p)
    return None


def frames(beats: list[Beat], w: int, h: int, fps: int = 30):
    """Yield one JPEG per frame for the whole timeline."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MotionError("playwright is not installed") from exc
    exe = find_chromium()
    quiet = type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda self, *a: None})
    server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: quiet(*a, directory=str(ASSETS), **k))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    story = {"beats": [{"type": b.type, "data": b.data, "theme": b.theme, "dur": b.dur} for b in beats]}
    total = max(1, round(sum(b.dur for b in beats) * fps))
    try:
        with sync_playwright() as pw:
            kwargs = {"executable_path": exe} if exe else {}
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"], **kwargs)
            try:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(f"{base}/stage.html")
                page.evaluate("(b) => window.loadFonts(b + '/fonts')", base)
                page.evaluate("([s, w, h]) => window.setup(s, w, h)", [story, w, h])
                grab = "(t) => { window.renderAt(t); return document.getElementById('c').toDataURL('image/jpeg', 0.92).slice(23); }"
                for n in range(total):
                    yield base64.b64decode(page.evaluate(grab, n / fps))
            finally:
                browser.close()
    except MotionError:
        raise
    except Exception as exc:
        raise MotionError(f"{exc.__class__.__name__}: {str(exc)[:200]}") from exc
    finally:
        server.shutdown()
