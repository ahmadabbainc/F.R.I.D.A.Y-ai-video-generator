"""Stock footage from Pexels or Pixabay (both free with an account).

fetch_clip() tries each provider that has a key and returns (path, provider)
for the first usable clip, or None so the caller can fall back to a generated
background. It never raises: a missing clip must not fail a video.
"""

from __future__ import annotations

from pathlib import Path

import requests

from .config import Settings

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"

# Used clip ids are tracked per provider so two scenes never show the same footage.
Used = set[tuple[str, int]]


def fetch_clip(
    keywords: str,
    aspect: str,
    dest: Path,
    settings: Settings,
    used: Used,
) -> tuple[Path, str] | None:
    if not keywords.strip():
        return None
    portrait = aspect == "9:16"
    providers = []
    if settings.pexels_api_key:
        providers.append(("Pexels", _pexels))
    if settings.pixabay_api_key:
        providers.append(("Pixabay", _pixabay))
    for name, search in providers:
        try:
            hit = search(keywords, portrait, settings, used)
            if hit:
                clip_id, url = hit
                _download(url, dest)
                used.add((name, clip_id))
                return dest, name
        except Exception:
            continue  # network, quota, odd response: try the next provider
    return None


def _pexels(keywords: str, portrait: bool, settings: Settings, used: Used) -> tuple[int, str] | None:
    resp = requests.get(
        PEXELS_SEARCH,
        headers={"Authorization": settings.pexels_api_key},
        params={"query": keywords, "orientation": "portrait" if portrait else "landscape", "per_page": 10, "size": "medium"},
        timeout=30,
    )
    resp.raise_for_status()
    for video in resp.json().get("videos", []):
        if ("Pexels", video["id"]) in used:
            continue
        link = _pick_pexels_file(video.get("video_files", []))
        if link:
            return video["id"], link
    return None


def _pick_pexels_file(files: list[dict]) -> str | None:
    """Prefer an mp4 close to 1080 on the long side; smaller downloads render faster."""
    mp4s = [f for f in files if f.get("file_type") == "video/mp4" and f.get("link")]
    if not mp4s:
        return None
    mp4s.sort(key=lambda f: abs(max(f.get("width", 0), f.get("height", 0)) - 1920))
    return mp4s[0]["link"]


def _pixabay(keywords: str, portrait: bool, settings: Settings, used: Used) -> tuple[int, str] | None:
    resp = requests.get(
        PIXABAY_SEARCH,
        params={"key": settings.pixabay_api_key, "q": keywords[:100], "per_page": 20, "safesearch": "true", "video_type": "film"},
        timeout=30,
    )
    resp.raise_for_status()
    candidates = []
    wanted = {w.lower().rstrip("s") for w in keywords.split() if len(w) > 2}
    for hit in resp.json().get("hits", []):
        if ("Pixabay", hit["id"]) in used:
            continue
        pick = _pick_pixabay_file(hit.get("videos", {}))
        if pick:
            url, width, height = pick
            # Pixabay has no orientation filter, so rank matching clips first.
            tags = {t.strip().lower().rstrip("s") for t in str(hit.get("tags", "")).replace(" ", ",").split(",") if t.strip()}
            relevance = len(wanted & tags)  # how many of the scene's words the clip is tagged with
            candidates.append((-relevance, 0 if (height > width) == portrait else 1, hit["id"], url))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[:2])  # best tag match, then orientation; stable keeps popularity order
    return candidates[0][2], candidates[0][3]


def _pick_pixabay_file(videos: dict) -> tuple[str, int, int] | None:
    """Medium is about 1080p. Skip 'large' (often 4K) because it is slow to download and render."""
    for size in ("medium", "small", "large", "tiny"):
        v = videos.get(size) or {}
        if v.get("url"):
            return v["url"], int(v.get("width") or 0), int(v.get("height") or 0)
    return None


def _download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
