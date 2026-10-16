"""Turn a title and topic into scenes: narration plus a footage search phrase."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from .config import Settings

WORDS_PER_SECOND = 2.5  # about 150 words a minute


@dataclass(frozen=True)
class Scene:
    narration: str
    keywords: str


def scene_count(seconds: int) -> int:
    return max(4, min(14, round(seconds / 6)))


def make_script(
    title: str,
    topic: str,
    seconds: int,
    settings: Settings,
    style_hint: str = "",
) -> tuple[list[Scene], list[str]]:
    """Return (scenes, warnings). Falls back to the demo script if the LLM fails."""
    warnings: list[str] = []
    if settings.live_script:
        try:
            return _llm_script(title, topic, seconds, settings, style_hint), warnings
        except Exception as exc:  # network, quota, bad JSON: never kill the job
            warnings.append(f"Script writer unavailable, used a template instead ({exc.__class__.__name__}).")
    else:
        warnings.append("No script key set, used a template script. Add FRIDAY_LLM_API_KEY for real scripts.")
    return demo_script(title, topic, seconds), warnings


def _llm_script(title: str, topic: str, seconds: int, settings: Settings, style_hint: str) -> list[Scene]:
    n = scene_count(seconds)
    words = int(seconds * WORDS_PER_SECOND)
    system = (
        "You write narration for short vertical videos. Reply with JSON only, no prose, "
        'in the shape {"scenes":[{"narration":"...","keywords":"..."}]}. '
        "Each keywords value is 1 to 3 plain words describing footage to show (concrete things you can film)."
    )
    user = (
        f"Title: {title}\nTopic: {topic}\n"
        f"Write exactly {n} scenes, about {words} words of narration in total. "
        "Open with a hook in the first scene and end with a clear closing line. "
        "Plain spoken language, no stage directions, no emojis."
    )
    if style_hint:
        user += f"\nStyle notes: {style_hint}"
    resp = requests.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": settings.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.8,
        },
        timeout=90,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_scenes(content)


def parse_scenes(content: str) -> list[Scene]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start : end + 1])
    scenes = [
        Scene(str(s["narration"]).strip(), str(s.get("keywords", "")).strip())
        for s in data["scenes"]
        if str(s.get("narration", "")).strip()
    ]
    if not scenes:
        raise ValueError("empty script")
    return scenes


def demo_script(title: str, topic: str, seconds: int) -> list[Scene]:
    """Deterministic template so the whole pipeline runs with no keys."""
    title = title.strip().rstrip(".!?")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", topic.strip()) if s.strip()]
    target = scene_count(seconds)
    closing = "Save this for later and share it with someone who needs it."
    filler = [
        f"Here is what matters most about {title.lower()}.",
        "Start small and keep it simple.",
        "A little progress each day adds up fast.",
        "Focus on one thing at a time.",
        "Small habits beat big plans.",
        "Check your progress every week.",
        "Keep what works and drop what doesn't.",
        "You don't need to be perfect to begin.",
        "Most people skip this step, and it shows.",
        "Take it one day at a time.",
        "Consistency is what makes it work.",
        "The first step is always the hardest.",
    ]
    # Title first, the closing line last, and exactly `target` scenes in between.
    body = ([f"{title}."] + sentences)[: target - 1]
    for extra in filler:
        if len(body) >= target - 1:
            break
        body.append(extra)
    lines = body + [closing]
    words = re.findall(r"[A-Za-z]{4,}", f"{title} {topic}")
    keyword = " ".join(words[:2]) or "abstract background"
    return [Scene(line, keyword) for line in lines]
