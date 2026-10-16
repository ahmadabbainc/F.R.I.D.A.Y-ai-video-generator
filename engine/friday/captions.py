"""Burned-in captions as an ASS file. Timing is proportional to text length within each scene."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Timed:
    start: float
    speech: float  # seconds of actual narration in this scene
    text: str


def chunk_words(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _stamp(t: float) -> str:
    cs = max(0, round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(scenes: list[Timed], width: int, height: int, font: str) -> str:
    portrait = height > width
    size = round(height * (0.052 if portrait else 0.06))
    outline = max(2, round(size * 0.09))
    margin_v = round(height * (0.2 if portrait else 0.08))
    margin_h = round(width * 0.08)
    max_chars = 20 if portrait else 38

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{size},&H00FFFFFF,&H000000FF,&H00141414,&H80000000,1,0,0,0,100,100,0,0,1,"
        f"{outline},2,2,{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for scene in scenes:
        chunks = chunk_words(scene.text, max_chars)
        total = sum(len(c) for c in chunks) or 1
        cursor = scene.start
        for chunk in chunks:
            span = scene.speech * len(chunk) / total
            lines.append(f"Dialogue: 0,{_stamp(cursor)},{_stamp(cursor + span)},Cap,,0,0,0,,{_escape(chunk)}")
            cursor += span
    return "\n".join(lines) + "\n"
