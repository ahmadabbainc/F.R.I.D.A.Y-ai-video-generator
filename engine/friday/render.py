"""ffmpeg steps: scene segments, exact-length audio, final assembly with captions."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

# Pairs of colours for generated backgrounds, used when no stock clip is available.
GRADIENTS = [
    ("0x0E2A3A", "0x1FB6FF"),
    ("0x1B1035", "0x7C5CFF"),
    ("0x10302A", "0x2FD3A0"),
    ("0x2A1424", "0xFF6B8A"),
]


class RenderError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-6:])
        raise RenderError(f"ffmpeg failed: {tail}")


def dimensions(aspect: str, scale: float) -> tuple[int, int]:
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080)

    def even(v: float) -> int:
        n = max(2, round(v * scale))
        return n + (n % 2)

    return even(w), even(h)


COMMON_OUT = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30"]


def build_segment(clip: Path | None, index: int, duration: float, w: int, h: int, out: Path) -> None:
    if clip is not None:
        fit = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,eq=brightness=-0.05"
        run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(clip),
             "-t", f"{duration:.3f}", "-vf", fit, *COMMON_OUT, str(out)]
        )
        return
    c0, c1 = GRADIENTS[index % len(GRADIENTS)]
    try:
        src = f"gradients=s={w}x{h}:c0={c0}:c1={c1}:x0=0:y0=0:x1={w}:y1={h}:speed=0.015:rate=30:duration={duration:.3f}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, *COMMON_OUT, str(out)])
    except RenderError:
        src = f"color=c={c0}:s={w}x{h}:r=30:d={duration:.3f}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, *COMMON_OUT, str(out)])


def encode_frames(frames: Iterable[bytes], w: int, h: int, out: Path) -> None:
    """Pipe raw RGB frames into ffmpeg and encode them as one segment."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", "30", "-i", "-", *COMMON_OUT, str(out)]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        try:
            for frame in frames:
                proc.stdin.write(frame)
        except BrokenPipeError:
            pass  # ffmpeg stopped early: its error is reported below
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
            code = proc.wait()
        if code != 0:
            err.seek(0)
            tail = "\n".join(err.read().decode(errors="replace").strip().splitlines()[-6:])
            raise RenderError(f"ffmpeg failed: {tail}")


def encode_jpegs(frames: Iterable[bytes], out: Path) -> None:
    """Pipe JPEG frames (from the browser renderer) into ffmpeg as one segment."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", "30", "-c:v", "mjpeg", "-i", "-",
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", *COMMON_OUT, str(out)]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        try:
            for frame in frames:
                proc.stdin.write(frame)
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
            code = proc.wait()
        if code != 0:
            err.seek(0)
            tail = "\n".join(err.read().decode(errors="replace").strip().splitlines()[-6:])
            raise RenderError(f"ffmpeg failed: {tail}")


def build_scene_audio(voice: Path, duration: float, out: Path) -> None:
    """Pad or trim narration to exactly `duration` so audio and video stay in sync."""
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice),
         "-af", f"apad=whole_dur={duration:.3f}", "-t", f"{duration:.3f}",
         "-ar", "44100", "-ac", "1", str(out)]
    )


def _concat_list(paths: list[Path], dest: Path) -> None:
    dest.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))


def assemble(segments: list[Path], audios: list[Path], ass_name: str, out: Path, workdir: Path) -> None:
    vlist, alist = workdir / "video.txt", workdir / "audio.txt"
    _concat_list(segments, vlist)
    _concat_list(audios, alist)
    run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(vlist),
         "-f", "concat", "-safe", "0", "-i", str(alist),
         "-vf", f"ass={ass_name}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)],
        cwd=workdir,  # relative ass path avoids filter-string escaping
    )
