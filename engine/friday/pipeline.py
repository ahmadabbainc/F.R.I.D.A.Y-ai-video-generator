"""The whole job: script, footage, voice, captions, render."""

from __future__ import annotations

import math
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import captions, explainer, footage, inspire, motion, render, scenes, script, voice
from .config import Settings

Progress = Callable[[int, str], None]


@dataclass
class Request:
    title: str
    topic: str = ""
    aspect: str = "9:16"  # "9:16" or "16:9"
    seconds: int = 45
    style_url: str = ""
    kind: str = "footage"  # "footage", "explainer" (animated) or "motion"


@dataclass
class Result:
    video: Path
    duration: float
    scenes: int
    warnings: list[str] = field(default_factory=list)


def _queries(keywords: str, title: str) -> list[str]:
    """Best search first, then each word alone, then the video's own theme."""
    words = keywords.split()
    out = [keywords] + (words if len(words) > 1 else [])
    theme = " ".join(w for w in title.split() if len(w) > 3)[:60]
    if theme:
        out.append(theme)
    seen: list[str] = []
    return [q for q in out if q.strip() and not (q in seen or seen.append(q))]


def _explainer(title, topic, seconds, aspect, out, work, settings, step, warnings, style_hint, rate) -> Result:
    """Animated explainer: every scene is drawn by code from the storyboard."""
    step(10, "Writing the storyboard")
    beats, warns = explainer.make_storyboard(title, topic, seconds, settings, style_hint)
    warnings += warns
    if beats[-1].type != "title":  # end on a closing title card instead of just stopping
        beats.append(explainer.Beat(f"That is {title}, explained.", "title", {"title": motion._short(title, 60), "subtitle": ""}))
    w, h = render.dimensions(aspect, settings.render_scale)
    segments, audios, timed = [], [], []
    silent, cursor, total = 0, 0.0, len(beats)
    for i, beat in enumerate(beats):
        step(20 + int(60 * i / total), f"Animating scene {i + 1} of {total}")
        audio_path, speech, spoken = voice.synthesize(beat.narration, work / f"voice_{i}", settings, rate)
        silent += 0 if spoken else 1
        frames = max(1, math.ceil(max(speech + 0.45, 3.4) * scenes.FPS))  # never shorter than the animation needs
        duration = frames / scenes.FPS  # whole frames, so picture and sound stay in step
        seg = work / f"seg_{i}.mp4"
        try:
            render.encode_frames(scenes.render_frames(beat.type, beat.data, duration, cursor, w, h), w, h, seg)
        except Exception:  # one bad scene must not sink the video: show its words plainly instead
            fallback = {"text": motion.headline(beat.narration, 8) or "Next", "highlight": []}
            render.encode_frames(scenes.render_frames("statement", fallback, duration, cursor, w, h), w, h, seg)
        segments.append(seg)
        padded = work / f"audio_{i}.wav"
        render.build_scene_audio(audio_path, duration, padded)
        audios.append(padded)
        timed.append(captions.Timed(cursor, speech, beat.narration))
        cursor += duration
    if silent == total:
        warnings.append("Voice service unreachable, so this video is silent.")
    elif silent:
        warnings.append(f"{silent} of {total} scenes had no voice because the voice service failed. Try again.")
    step(85, "Rendering")
    out.parent.mkdir(parents=True, exist_ok=True)
    render.assemble(segments, audios, None, out, work)  # animated scenes carry their own words: no captions
    step(100, "Done")
    return Result(out, cursor, total, warnings)


def _motion(title, topic, seconds, aspect, out, work, settings, step, warnings, style_hint, rate) -> Result:
    """Motion video: voice first, then one browser-drawn timeline that matches it exactly."""
    step(10, "Writing the storyboard")
    beats, warns = motion.make_storyboard(title, topic, seconds, settings, style_hint)
    warnings += warns
    w, h = render.dimensions(aspect, settings.render_scale)
    audios, timed, silent, cursor, total = [], [], 0, 0.0, len(beats)
    for i, beat in enumerate(beats):
        step(15 + int(35 * i / total), f"Recording voice {i + 1} of {total}")
        audio_path, speech, spoken = voice.synthesize(beat.narration, work / f"voice_{i}", settings, rate)
        silent += 0 if spoken else 1
        hold = 1.0 if i == total - 1 else 0.45  # the closing scene lingers a moment before the video ends
        beat.dur = math.ceil(max(speech + hold, 3.6 if i == total - 1 else 3.2) * scenes.FPS) / scenes.FPS
        padded = work / f"audio_{i}.wav"
        render.build_scene_audio(audio_path, beat.dur, padded)
        audios.append(padded)
        timed.append(captions.Timed(cursor, speech, beat.narration))
        cursor += beat.dur
    if silent == total:
        warnings.append("Voice service unreachable, so this video is silent.")
    elif silent:
        warnings.append(f"{silent} of {total} scenes had no voice because the voice service failed. Try again.")
    if settings.live_script:
        step(50, "Designing custom animation for each scene")
        try:
            if motion.add_code(beats, aspect, settings):
                problems = motion.check_code(beats, w, h)
                if problems:
                    motion.repair_code(beats, {i: p for i, p in problems.items()}, aspect, settings)
        except motion.MotionError:
            for b in beats:
                b.code = ""
    step(62, "Animating the motion scenes")
    seg = work / "motion.mp4"
    report: list[str] = []
    try:
        render.encode_jpegs(motion.frames(beats, w, h, report=report), seg)
    except (motion.MotionError, render.RenderError) as exc:
        if not any(b.code for b in beats):
            raise RuntimeError(f"Motion renderer failed: {exc}") from exc
        for b in beats:  # custom code must never sink the video: render again with the built-in scenes
            b.code = ""
        report = []
        warnings.append("Custom animation caused a problem, so built-in scenes were used.")
        try:
            render.encode_jpegs(motion.frames(beats, w, h, report=report), seg)
        except (motion.MotionError, render.RenderError) as exc2:
            raise RuntimeError(f"Motion renderer failed: {exc2}") from exc2
    coded = next((r.split() for r in report if r.startswith("__coded")), None)
    if coded and int(coded[1]):
        ok = int(coded[1]) - int(coded[2])
        warnings.append(f"Custom AI animation on {ok} of {total} scenes; the others use built-in looks.")
    step(85, "Rendering")
    out.parent.mkdir(parents=True, exist_ok=True)
    render.assemble([seg], [work / f"audio_{i}.wav" for i in range(total)], None, out, work)
    step(100, "Done")
    return Result(out, cursor, total, warnings)


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
    if req.kind in ("motion", "explainer") and aspect != "9:16":
        aspect = "9:16"  # animated videos are always vertical, so every one looks the same
        warnings.append("Animated and Motion videos are always vertical.")
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

        if req.kind == "motion":
            return _motion(title, topic, seconds, aspect, out, work, settings, step, warnings, style_hint, rate)
        if req.kind == "explainer":
            return _explainer(title, topic, seconds, aspect, out, work, settings, step, warnings, style_hint, rate)

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
        silent_scenes = 0
        total = len(scenes)

        for i, scene in enumerate(scenes):
            step(20 + int(60 * i / total), f"Building scene {i + 1} of {total}")
            audio_path, speech, spoken = voice.synthesize(scene.narration, work / f"voice_{i}", settings, rate)
            silent_scenes += 0 if spoken else 1
            duration = round(speech + 0.45, 3)  # small breath between scenes

            queries = _queries(scene.keywords, title)
            found = None
            for n, query in enumerate(queries):
                # Open libraries go first for "real" scenes, and last (as a fallback) for everything else.
                use_open = (scene.real and n == 0) or (not scene.real and n == len(queries) - 1)
                found = footage.fetch_clip(
                    query, aspect, work / f"clip_{i}.mp4", settings, used,
                    search=scene.search if (scene.real and n == 0) else "", real=scene.real and n == 0, open_libs=use_open,
                    min_seconds=duration,
                )
                if found:
                    break
            clip = found[0] if found else None
            if found:
                credits.add(found[1])
            seg = work / f"seg_{i}.mp4"
            try:
                render.build_segment(clip, i, duration, w, h, seg)
            except render.RenderError:
                if clip is None:
                    raise
                credits.discard(found[1])  # unreadable clip: use a generated background instead
                render.build_segment(None, i, duration, w, h, seg)
            segments.append(seg)

            padded = work / f"audio_{i}.wav"
            render.build_scene_audio(audio_path, duration, padded)
            audios.append(padded)

            timed.append(captions.Timed(cursor, speech, scene.narration))
            cursor += duration

        if silent_scenes == total:
            warnings.append("Voice service unreachable, so this video is silent.")
        elif silent_scenes:
            warnings.append(f"{silent_scenes} of {total} scenes had no voice because the voice service failed. Try again.")
        if not settings.live_footage and not credits:
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
