"""Optional: learn the *style* of a reference video from its transcript.

Only pacing and structure are used (speed, sentence length, how it opens, how
directly it addresses the viewer). The reference's words are never reused.
Everything here is best effort: if anything fails, Friday just carries on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class StyleProfile:
    words_per_minute: int
    avg_sentence_words: float
    hook: str  # "question", "number", "bold claim" or "plain"
    talks_to_viewer: bool

    @property
    def voice_rate_percent(self) -> int:
        """Map reference pace to a speech rate change, kept in a safe range."""
        return max(-15, min(25, round((self.words_per_minute / 150 - 1) * 100)))

    def hint(self) -> str:
        pace = "fast" if self.words_per_minute >= 170 else "relaxed" if self.words_per_minute <= 130 else "steady"
        parts = [f"Pace is {pace}."]
        if self.avg_sentence_words <= 10:
            parts.append("Use short, punchy sentences.")
        elif self.avg_sentence_words >= 18:
            parts.append("Use longer, flowing sentences.")
        parts.append(
            {
                "question": "Open with a question.",
                "number": "Open with a specific number or statistic.",
                "bold claim": "Open with a bold, surprising claim.",
                "plain": "Open with a plain, direct statement.",
            }[self.hook]
        )
        if self.talks_to_viewer:
            parts.append("Speak directly to the viewer using 'you'.")
        return " ".join(parts)


def extract_video_id(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0] or None
    if host in {"youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            return (parse_qs(parsed.query).get("v") or [None])[0]
        match = re.match(r"^/(?:shorts|embed|live)/([\w-]{6,})", parsed.path)
        if match:
            return match.group(1)
    return None


def analyze(entries: list[tuple[float, float, str]]) -> StyleProfile | None:
    """entries: (start_seconds, duration_seconds, text) caption chunks."""
    text = " ".join(t for _, _, t in entries).replace("\n", " ").strip()
    words = text.split()
    if len(words) < 30 or not entries:
        return None
    span = (entries[-1][0] + entries[-1][1]) - entries[0][0]
    if span <= 5:
        return None
    wpm = round(len(words) / (span / 60))
    sentences = [s for s in re.split(r"[.!?]+\s+", text) if s.split()]
    avg = len(words) / max(1, len(sentences)) if len(sentences) > 2 else min(len(words), 14)
    first = " ".join(words[:25])
    if "?" in first or re.match(r"^(what|why|how|did|do|have|ever|imagine)\b", first.lower()):
        hook = "question"
    elif re.search(r"\d", " ".join(words[:12])):
        hook = "number"
    elif re.search(r"\b(never|nobody|everyone|secret|truth|wrong|stop|biggest|worst|best)\b", first.lower()):
        hook = "bold claim"
    else:
        hook = "plain"
    you = len(re.findall(r"\b(you|your|you're|you'll)\b", text.lower()))
    return StyleProfile(wpm, round(avg, 1), hook, you / len(words) > 0.01)


def fetch_entries(video_id: str) -> list[tuple[float, float, str]]:
    from youtube_transcript_api import YouTubeTranscriptApi  # optional dependency

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        return [(float(s.start), float(s.duration), s.text) for s in fetched]
    except AttributeError:  # older library versions
        raw = YouTubeTranscriptApi.get_transcript(video_id)
        return [(float(r["start"]), float(r["duration"]), r["text"]) for r in raw]


def learn_style(url: str) -> tuple[StyleProfile | None, str | None]:
    """Return (profile, warning). Never raises."""
    video_id = extract_video_id(url)
    if not video_id:
        return None, "That doesn't look like a YouTube link, so the style reference was skipped."
    try:
        profile = analyze(fetch_entries(video_id))
    except Exception:
        return None, "Couldn't read that video's captions, so the style reference was skipped."
    if profile is None:
        return None, "That video has too little spoken content to learn a style from."
    return profile, None
