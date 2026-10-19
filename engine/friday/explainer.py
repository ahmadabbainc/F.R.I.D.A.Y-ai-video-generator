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

from . import script
from .config import Settings


@dataclass(frozen=True)
class Beat:
    narration: str
    type: str = "statement"
    data: dict = field(default_factory=dict)


TYPES = ("title", "statement", "big_number", "bars", "line", "timeline", "points")
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


def _statement(narration: str) -> Beat:
    return Beat(narration, "statement", {"text": _clip(narration, 130), "highlight": []})


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
        return Beat(narration, kind, {"text": text, "highlight": hl})

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


SYSTEM = """You write short animated explainer videos. Every scene has narration (spoken aloud) and a visual that is drawn by code, so the visual must show exactly what the narration says.
Reply with JSON only: {"scenes":[{"narration":"...","type":"...","data":{...}}]}
Scene types and their data:
- title: {"title":"short title","subtitle":"optional short line"}. Use for the first scene only.
- statement: {"text":"the key sentence, at most 14 words","highlight":["1-3 key words from text"]}. Always works; use it for ideas with no numbers.
- big_number: {"label":"what the number measures","value":1234,"prefix":"$","suffix":"M","caption":"optional note"}. One striking figure.
- bars: {"title":"...","prefix":"","suffix":"%","items":[{"label":"short name","value":12}]} with 3 to 5 items. Compares amounts.
- line: {"title":"...","prefix":"","suffix":"","points":[{"label":"2019","value":10}]} with 4 to 7 points. A trend over time.
- timeline: {"title":"...","events":[{"when":"2008","what":"short event"}]} with 3 to 5 events.
- points: {"title":"...","items":["short point","short point"]} with 3 to 4 items. Lists, tips, steps.
Rules:
- Use numbers, dates and statistics ONLY when you are confident they are real and accurate. If you are not sure, use statement or points instead. Never invent figures.
- Vary the scene types. Do not use the same type more than twice in a row.
- End with a statement scene that closes the video.
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
    """No key: a title card, then each template sentence as an animated statement."""
    lines = [s.narration for s in script.demo_script(title, topic, seconds)]
    beats = [Beat(lines[0], "title", {"title": _clip(title, 80), "subtitle": ""})]
    beats += [_statement(line) for line in lines[1:]]
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
