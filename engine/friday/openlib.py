"""Openly licensed footage libraries: NASA, Wikimedia Commons, Internet Archive.

No keys needed. Every search returns (clip_id, download_url, credit) for a clip
whose licence allows reuse (public domain, CC0 or CC BY), or None. Anything with
an unclear or restrictive licence (NC, ND, SA, "all rights reserved") is skipped.
The credit line is shown in the video's notes, as the licences ask.
Each function may raise; footage.fetch_clip catches that and moves on.
"""

from __future__ import annotations

import re
import zlib

import requests

MAX_BYTES = 80 * 1024 * 1024  # skip huge originals: slow to download and render
HEADERS = {"User-Agent": "Friday-video-maker/1.0 (open-source; contact via GitHub)"}

NASA_SEARCH = "https://images-api.nasa.gov/search"
NASA_ASSET = "https://images-api.nasa.gov/asset/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
ARCHIVE_META = "https://archive.org/metadata/"
ARCHIVE_DL = "https://archive.org/download/"

Hit = tuple[int, str, str]  # (stable id for the used-set, url, credit text)


def stable_id(text: str) -> int:
    return zlib.crc32(text.encode("utf-8"))


def _get_json(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _terms(query: str) -> str:
    return " ".join(re.findall(r"[A-Za-z0-9]+", query))[:100]


# ---- NASA (public domain; NASA asks that use not imply endorsement) -------------

def pick_nasa_file(urls: list[str]) -> str | None:
    """Prefer the medium or mobile rendition; skip originals, previews and non-mp4 files."""
    mp4 = [u for u in urls if u.lower().endswith(".mp4") and "~orig" not in u and "~preview" not in u]
    for tag in ("~medium", "~mobile", "~small"):
        for u in mp4:
            if tag in u:
                return u.replace("http://", "https://")
    return mp4[0].replace("http://", "https://") if mp4 else None


def nasa(query: str, portrait: bool, used: set) -> Hit | None:
    data = _get_json(NASA_SEARCH, {"q": _terms(query), "media_type": "video"})
    for item in data.get("collection", {}).get("items", [])[:6]:
        meta = (item.get("data") or [{}])[0]
        nid = meta.get("nasa_id")
        if not nid or ("NASA", stable_id(nid)) in used:
            continue
        assets = _get_json(NASA_ASSET + requests.utils.quote(nid))
        urls = [i.get("href", "") for i in assets.get("collection", {}).get("items", [])]
        url = pick_nasa_file(urls)
        if url:
            return stable_id(nid), url, "NASA"
    return None


# ---- Wikimedia Commons (licence is checked per file) -----------------------------

_OK_LICENCE = re.compile(r"^(cc0|pd\b|public domain|cc[- ]by[- ]\d)", re.I)


def licence_ok(short_name: str) -> bool:
    """True for public domain, CC0 and plain CC BY. False for SA, NC, ND and anything unclear."""
    return bool(_OK_LICENCE.match((short_name or "").strip()))


def _plain(html: str, limit: int = 60) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()[:limit]


def commons(query: str, portrait: bool, used: set) -> Hit | None:
    data = _get_json(
        COMMONS_API,
        {
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"filetype:video {_terms(query)}", "gsrlimit": 12,
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        },
    )
    pages = sorted((data.get("query", {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licence = (meta.get("LicenseShortName") or {}).get("value", "")
        url = info.get("url", "")
        if not url or not str(info.get("mime", "")).startswith("video/") or not licence_ok(licence):
            continue
        if int(info.get("size") or 0) > MAX_BYTES or ("Wikimedia Commons", stable_id(url)) in used:
            continue
        artist = _plain((meta.get("Artist") or {}).get("value", "")) or "unknown author"
        return stable_id(url), url, f"Wikimedia Commons ({artist}, {licence})"
    return None


# ---- Internet Archive (public-domain films only) ---------------------------------

def pick_archive_file(files: list[dict]) -> str | None:
    best = None
    for f in files:
        name = str(f.get("name", ""))
        if not name.lower().endswith(".mp4") or "thumb" in name.lower():
            continue
        size = int(f.get("size") or 0)
        if 0 < size <= MAX_BYTES and (best is None or size > best[1]):
            best = (name, size)  # biggest file under the cap is the best quality
    return best[0] if best else None


def archive(query: str, portrait: bool, used: set) -> Hit | None:
    terms = _terms(query)
    if not terms:
        return None
    data = _get_json(
        ARCHIVE_SEARCH,
        {
            "q": f"({terms}) AND mediatype:movies AND licenseurl:*publicdomain*",
            "fl[]": ["identifier", "title"], "rows": 6, "sort[]": "downloads desc", "output": "json",
        },
    )
    for doc in data.get("response", {}).get("docs", []):
        ident = doc.get("identifier")
        if not ident or ("Internet Archive", stable_id(ident)) in used:
            continue
        name = pick_archive_file(_get_json(ARCHIVE_META + requests.utils.quote(ident)).get("files", []))
        if name:
            title = _plain(str(doc.get("title", ident)), 50)
            return stable_id(ident), f"{ARCHIVE_DL}{requests.utils.quote(ident)}/{requests.utils.quote(name)}", \
                f"Internet Archive ({title}, public domain)"
    return None


# name used in the used-set, search function
LIBRARIES = {"NASA": nasa, "Wikimedia Commons": commons, "Internet Archive": archive}
