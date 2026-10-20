"""Storyboards for animated explainer videos.

The AI (or, with no key, a plain template) writes each scene's narration plus a
small, structured description of what to draw. Everything the AI returns is
checked and cleaned here, and anything unusable becomes a plain text scene, so a
bad answer can never break the video.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import icons, script
from .config import Settings


@dataclass(frozen=True)
class Beat:
    narration: str
    type: str = "statement"
    data: dict = field(default_factory=dict)


TYPES = ("title", "statement", "icon", "big_number", "bars", "line", "timeline", "points", "flow", "compare", "orbit")
FACT_TYPES = {"big_number", "bars", "line", "timeline"}  # scenes that show numbers or dates


def _clip(v, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def _num(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        out = float(v)
    else:
        try:
            out = float(re.sub(r"[,\s$€£%]", "", str(v)))
        except ValueError:
            return None
    return out if out == out and abs(out) < 1e15 else None  # not NaN, not absurd


def _icon(name, *context: str) -> str:
    """A valid icon name: the one given, else the best guess from the surrounding words, else ''."""
    n = str(name or "").strip().lower()
    return n if n in icons.ICONS else icons.guess(" ".join(context))


def _statement(narration: str, icon: str = "") -> Beat:
    return Beat(narration, "statement", {"text": _clip(narration, 130), "highlight": [], "icon": _icon(icon, narration)})


def sanitize_beat(raw: dict) -> Beat | None:
    """Turn one AI-written scene into a safe Beat. Returns None if there is no narration."""
    if not isinstance(raw, dict):
        return None
    narration = _clip(raw.get("narration"), 400)
    if not narration:
        return None
    kind = str(raw.get("type", "statement")).strip().lower()
    d = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    if kind not in TYPES:
        return _statement(narration)

    if kind == "title":
        return Beat(narration, kind, {"title": _clip(d.get("title"), 80) or _clip(narration, 60), "subtitle": _clip(d.get("subtitle"), 90)})

    if kind == "statement":
        text = _clip(d.get("text"), 130) or _clip(narration, 130)
        hl = [_clip(h, 30) for h in d.get("highlight", []) if isinstance(h, str)][:4] if isinstance(d.get("highlight"), list) else []
        return Beat(narration, kind, {"text": text, "highlight": hl, "icon": _icon(d.get("icon"), text, narration)})

    if kind == "big_number":
        value = _num(d.get("value"))
        if value is None or value < 0:
            return _statement(narration)
        return Beat(narration, kind, {
            "value": value, "label": _clip(d.get("label"), 80), "caption": _clip(d.get("caption"), 80),
            "prefix": _clip(d.get("prefix"), 4), "suffix": _clip(d.get("suffix"), 16),
        })

    if kind in ("bars", "line"):
        key = "items" if kind == "bars" else "points"
        rows = []
        for r in d.get(key, []) if isinstance(d.get(key), list) else []:
            if not isinstance(r, dict):
                continue
            v, label = _num(r.get("value")), _clip(r.get("label"), 28)
            if v is not None and label and (kind == "line" or v >= 0):
                rows.append({"label": label, "value": v})
        rows = rows[:6] if kind == "bars" else rows[:8]
        if len(rows) < (2 if kind == "bars" else 3):
            return _statement(narration)
        return Beat(narration, kind, {
            "title": _clip(d.get("title"), 70) or _clip(narration, 50), key: rows,
            "prefix": _clip(d.get("prefix"), 4), "suffix": _clip(d.get("suffix"), 16),
        })

    if kind == "timeline":
        events = []
        for r in d.get("events", []) if isinstance(d.get("events"), list) else []:
            if isinstance(r, dict) and _clip(r.get("when"), 14) and _clip(r.get("what"), 80):
                events.append({"when": _clip(r.get("when"), 14), "what": _clip(r.get("what"), 80)})
        if len(events) < 2:
            return _statement(narration)
        return Beat(narration, kind, {"title": _clip(d.get("title"), 70) or "Timeline", "events": events[:5]})

    if kind == "icon":
        label = _clip(d.get("label"), 60) or _clip(narration, 60)
        return Beat(narration, kind, {"icon": _icon(d.get("icon"), label, narration) or "star", "label": label, "caption": _clip(d.get("caption"), 80)})

    if kind == "flow":
        steps = []
        for r in d.get("steps", []) if isinstance(d.get("steps"), list) else []:
            r = {"label": r} if isinstance(r, str) else r
            label = _clip(r.get("label"), 24) if isinstance(r, dict) else ""
            if label:
                steps.append({"label": label, "icon": _icon(r.get("icon"), label) or "star"})
        if len(steps) < 2:
            return _statement(narration)
        return Beat(narration, kind, {"title": _clip(d.get("title"), 70) or "How it works", "steps": steps[:4]})

    if kind == "compare":
        sides = []
        for key in ("left", "right"):
            r = d.get(key) if isinstance(d.get(key), dict) else {}
            label = _clip(r.get("label"), 22)
            pts = [_clip(x, 44) for x in r.get("points", []) if isinstance(x, str) and _clip(x, 44)] if isinstance(r.get("points"), list) else []
            if label:
                sides.append({"label": label, "icon": _icon(r.get("icon"), label) or "star", "points": pts[:3]})
        if len(sides) < 2:
            return _statement(narration)
        return Beat(narration, kind, {"title": _clip(d.get("title"), 70), "left": sides[0], "right": sides[1]})

    if kind == "orbit":
        c = d.get("center") if isinstance(d.get("center"), dict) else {}
        label = _clip(c.get("label"), 22) or _clip(d.get("title"), 22)
        items = [_clip(x, 18) for x in d.get("items", []) if isinstance(x, str) and _clip(x, 18)] if isinstance(d.get("items"), list) else []
        if not label or len(items) < 3:
            return _statement(narration)
        return Beat(narration, kind, {"label": label, "icon": _icon(c.get("icon"), label, narration) or "star", "items": items[:6]})

    items = [_clip(i, 90) for i in d.get("items", []) if isinstance(i, str) and _clip(i, 90)] if isinstance(d.get("items"), list) else []
    if len(items) < 2:
        return _statement(narration)
    return Beat(narration, "points", {"title": _clip(d.get("title"), 70) or "Key points", "items": items[:5]})


def parse_storyboard(content: str) -> list[Beat]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    beats = [b for b in (sanitize_beat(s) for s in data["scenes"]) if b]
    if not beats:
        raise ValueError("empty storyboard")
    return beats


SYSTEM = """You write short animated explainer videos. Every scene has narration (spoken aloud) and a visual that is drawn and animated by code, so the visual must show exactly what the narration says.
Reply with JSON only: {"scenes":[{"narration":"...","type":"...","data":{...}}]}
Icons you can use (animated): rocket, coins, bulb, clock, heart, shield, lock, cart, house, gear, globe, star, growth, magnifier, person, check, phone.
Scene types and their data:
- title: {"title":"short title","subtitle":"optional short line"}. First scene only.
- icon: {"icon":"rocket","label":"short caption, at most 8 words","caption":"optional"}. One big animated icon with a caption. Great for a key idea.
- statement: {"text":"the key sentence, at most 14 words","highlight":["1-3 key words from text"],"icon":"optional icon name"}. Always works.
- flow: {"title":"...","steps":[{"icon":"cart","label":"2-3 words"}]} with 3 or 4 steps. A process or sequence.
- compare: {"title":"optional","left":{"label":"Rent","icon":"house","points":["short","short"]},"right":{"label":"Buy","icon":"coins","points":["short","short"]}}. Two options side by side.
- orbit: {"center":{"label":"Inflation","icon":"coins"},"items":["Prices","Wages","Savings","Interest"]} with 3 to 6 short items. A concept and the things connected to it.
- big_number: {"label":"what the number measures","value":1234,"prefix":"$","suffix":"M","caption":"optional note"}. One striking figure.
- bars: {"title":"...","prefix":"","suffix":"%","items":[{"label":"short name","value":12}]} with 3 to 5 items.
- line: {"title":"...","prefix":"","suffix":"","points":[{"label":"2019","value":10}]} with 4 to 7 points.
- timeline: {"title":"...","events":[{"when":"2008","what":"short event"}]} with 3 to 5 events.
- points: {"title":"...","items":["short point","short point"]} with 3 to 4 items.
Rules:
- Prefer the animated scenes (icon, flow, compare, orbit, statement with an icon). Use charts and numbers only when they genuinely help.
- Use numbers, dates and statistics ONLY when you are confident they are real and accurate. If not sure, use another type. Never invent figures.
- Vary the scene types. Never use the same type twice in a row.
- End with a statement or icon scene that closes the video.
- Plain spoken language, no stage directions, no emojis. Values are plain numbers (no units inside the number)."""


def llm_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> list[Beat]:
    n = script.scene_count(seconds)
    words = int(seconds * script.WORDS_PER_SECOND)
    user = (
        f"Title: {title}\nTopic: {topic}\n"
        f"Write exactly {n} scenes, about {words} words of narration in total. Open with a title scene and a hook."
    )
    if style_hint:
        user += f"\nStyle notes: {style_hint}"
    return parse_storyboard(script.chat(settings, SYSTEM, user))


def demo_storyboard(title: str, topic: str, seconds: int) -> list[Beat]:
    """No key: a title card, then each template sentence as an animated scene with a fitting icon."""
    lines = [s.narration for s in script.demo_script(title, topic, seconds)]
    beats = [Beat(lines[0], "title", {"title": _clip(title, 80), "subtitle": ""})]
    for i, line in enumerate(lines[1:], 1):
        icon = _icon("", line, title)
        if icon and i % 2 == 1:  # every other scene is a big animated icon, the rest are words with a small icon
            beats.append(Beat(line, "icon", {"icon": icon, "label": _clip(line, 60), "caption": ""}))
        else:
            beats.append(_statement(line, icon))
    return beats


def make_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> tuple[list[Beat], list[str]]:
    warnings: list[str] = []
    if settings.live_script:
        try:
            beats = llm_storyboard(title, topic, seconds, settings, style_hint)
            if any(b.type in FACT_TYPES for b in beats):
                warnings.append("Numbers and dates in animated videos are written by the AI. Check them before you publish.")
            return beats, warnings
        except Exception as exc:  # network, quota, bad JSON: never kill the job
            code = getattr(getattr(exc, "response", None), "status_code", "")
            warnings.append(f"Script writer unavailable, used a template instead ({exc.__class__.__name__} {code}).".replace(" )", ")"))
    else:
        warnings.append("No script key set, used a template script. Add FRIDAY_LLM_API_KEY for real scripts and charts.")
    return demo_storyboard(title, topic, seconds), warnings
