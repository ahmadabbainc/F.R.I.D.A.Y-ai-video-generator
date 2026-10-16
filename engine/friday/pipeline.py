"""The whole job: script, footage, voice, captions, render."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import captions, footage, inspire, render, script, voice
from .config import Settings

Progress = Callable[[int, str], None]


@dataclass
class Request:
    title: str
    topic: str = ""
    aspect: str = "9:16"  # "9:16" or "16:9"
    seconds: int = 45
    style_url: str = ""


@dataclass
class Result:
    video: Path
    duration: float
    scenes: int
    warnings: list[str] = field(default_factory=list)


def generate(req: Request, out: Path, settings: Settings, progress: Progress | None = None) -> Result:
    def step(pct: int, label: str) -> None:
        if progress:
            progress(pct, label)

    warnings: list[str] = []
    title = req.title.strip()
    if not title:
        raise ValueError("Add a title to start.")
    topic = req.topic.strip() or title
    seconds = max(15, min(90, req.seconds))
    aspect = req.aspect if req.aspect in ("9:16", "16:9") else "9:16"
    work = out.parent / f"{out.stem}_work"
    work.mkdir(parents=True, exist_ok=True)

    try:
        style_hint, rate = "", 0
        if req.style_url.strip():
            step(5, "Reading the style reference")
            profile, warn = inspire.learn_style(req.style_url)
            if warn:
                warnings.append(warn)
            if profile:
                style_hint, rate = profile.hint(), profile.voice_rate_percent

        step(10, "Writing the script")
        scenes, warns = script.make_script(title, topic, seconds, settings, style_hint)
        warnings += warns

        w, h = render.dimensions(aspect, settings.render_scale)
        segments: list[Path] = []
        audios: list[Path] = []
        timed: list[captions.Timed] = []
        used: footage.Used = set()
        credits: set[str] = set()
        cursor = 0.0
        spoke_any = False
        total = len(scenes)

        for i, scene in enumerate(scenes):
            step(20 + int(60 * i / total), f"Building scene {i + 1} of {total}")
            audio_path, speech, spoken = voice.synthesize(scene.narration, work / f"voice_{i}", settings, rate)
            spoke_any = spoke_any or spoken
            duration = round(speech + 0.45, 3)  # small breath between scenes

            found = footage.fetch_clip(scene.keywords, aspect, work / f"clip_{i}.mp4", settings, used)
            clip = found[0] if found else None
            if found:
                credits.add(found[1])
            seg = work / f"seg_{i}.mp4"
            render.build_segment(clip, i, duration, w, h, seg)
            segments.append(seg)

            padded = work / f"audio_{i}.wav"
            render.build_scene_audio(audio_path, duration, padded)
            audios.append(padded)

            timed.append(captions.Timed(cursor, speech, scene.narration))
            cursor += duration

        if not spoke_any:
            warnings.append("Voice service unreachable, so this video is silent. Captions are still burned in.")
        if not settings.live_footage:
            warnings.append("No footage key set, used generated backgrounds. Add PIXABAY_API_KEY (or PEXELS_API_KEY) for stock footage.")
        elif not credits:
            warnings.append("Couldn't fetch stock footage (key rejected, no matches, or the service was down), so generated backgrounds were used.")
        warnings += [f"Footage from {name}." for name in sorted(credits)]

        step(85, "Adding captions and rendering")
        (work / "captions.ass").write_text(captions.build_ass(timed, w, h, settings.caption_font), encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        render.assemble(segments, audios, "captions.ass", out, work)

        step(100, "Done")
        return Result(out, cursor, total, warnings)
    finally:
        shutil.rmtree(work, ignore_errors=True)
