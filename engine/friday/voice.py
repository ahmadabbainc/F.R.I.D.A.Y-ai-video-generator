"""Narration. Uses edge-tts (free, no key). Falls back to silence so a job never dies here."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .config import Settings
from .script import WORDS_PER_SECOND


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(out.strip())


def synthesize(text: str, dest_stem: Path, settings: Settings, rate_percent: int = 0) -> tuple[Path, float, bool]:
    """Return (audio_path, duration_seconds, spoken). spoken is False for the silent fallback."""
    mp3 = dest_stem.with_suffix(".mp3")
    try:
        asyncio.run(_edge(text, settings.voice, mp3, rate_percent))
        duration = probe_duration(mp3)
        if duration > 0.2:
            return mp3, duration, True
    except Exception:
        pass
    wav = dest_stem.with_suffix(".wav")
    return wav, _silence(text, wav), False


async def _edge(text: str, voice: str, dest: Path, rate_percent: int) -> None:
    import edge_tts

    rate = f"{rate_percent:+d}%"
    await edge_tts.Communicate(text, voice, rate=rate).save(str(dest))


def _silence(text: str, dest: Path) -> float:
    words = max(1, len(text.split()))
    duration = max(2.0, words / WORDS_PER_SECOND)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{duration:.2f}", str(dest),
        ],
        check=True,
        capture_output=True,
    )
    return duration
