"""Stock footage from Pexels (free API key). Returns None when nothing is found."""

from __future__ import annotations

from pathlib import Path

import requests

from .config import Settings

PEXELS_SEARCH = "https://api.pexels.com/videos/search"


def fetch_clip(
    keywords: str,
    aspect: str,
    dest: Path,
    settings: Settings,
    used: set[int],
) -> Path | None:
    if not settings.live_footage or not keywords:
        return None
    orientation = "portrait" if aspect == "9:16" else "landscape"
    try:
        resp = requests.get(
            PEXELS_SEARCH,
            headers={"Authorization": settings.pexels_api_key},
            params={"query": keywords, "orientation": orientation, "per_page": 10, "size": "medium"},
            timeout=30,
        )
        resp.raise_for_status()
        for video in resp.json().get("videos", []):
            if video["id"] in used:
                continue
            link = _pick_file(video.get("video_files", []))
            if not link:
                continue
            _download(link, dest)
            used.add(video["id"])
            return dest
    except Exception:
        return None
    return None


def _pick_file(files: list[dict]) -> str | None:
    """Prefer an mp4 close to 1080 on the long side; smaller downloads render faster."""
    mp4s = [f for f in files if f.get("file_type") == "video/mp4" and f.get("link")]
    if not mp4s:
        return None
    mp4s.sort(key=lambda f: abs(max(f.get("width", 0), f.get("height", 0)) - 1920))
    return mp4s[0]["link"]


def _download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
