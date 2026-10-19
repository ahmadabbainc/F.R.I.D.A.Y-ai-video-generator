"""Narration. Uses edge-tts (free, no key). Falls back to silence so a job never dies here."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
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


PAUSE_SECONDS = 1.5  # tests set this to 0
BACKUP_VOICES = ["en-US-GuyNeural", "en-GB-RyanNeural"]


def synthesize(text: str, dest_stem: Path, settings: Settings, rate_percent: int = 0) -> tuple[Path, float, bool]:
    """Return (audio_path, duration_seconds, spoken). spoken is False for the silent fallback.

    Order: the chosen edge-tts voice (retried), backup edge-tts voices, an offline
    espeak-ng voice, and only then silence.
    """
    mp3 = dest_stem.with_suffix(".mp3")
    voices = [settings.voice] + [v for v in BACKUP_VOICES if v != settings.voice]
    for attempt, voice in enumerate([voices[0], voices[0]] + voices[1:]):
        try:
            asyncio.run(_edge(text, voice, mp3, rate_percent))
            duration = probe_duration(mp3)
            if duration > 0.2:
                return mp3, duration, True
        except Exception:
            pass
        time.sleep(PAUSE_SECONDS * (attempt + 1))
    wav = dest_stem.with_suffix(".wav")
    if _espeak(text, wav, rate_percent):
        try:
            duration = probe_duration(wav)
            if duration > 0.2:
                return wav, duration, True
        except Exception:
            pass
    return wav, _silence(text, wav), False


def _espeak(text: str, dest: Path, rate_percent: int) -> bool:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return False
    wpm = max(110, min(240, int(165 * (1 + rate_percent / 100))))
    try:
        subprocess.run([exe, "-v", "en-us", "-s", str(wpm), "-w", str(dest), "--", text],
                       check=True, capture_output=True, timeout=60)
        return dest.exists() and dest.stat().st_size > 1000
    except Exception:
        return False


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
