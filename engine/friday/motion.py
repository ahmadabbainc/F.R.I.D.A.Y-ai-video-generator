"""Motion videos: bold kinetic typography, 3D and UI-style scenes, drawn in a headless browser.

The AI (or a template, with no key) writes a storyboard of scene types. Each scene is
checked and cleaned here, so a bad answer can never break the video. The browser page
in motion_assets draws any frame from a time value; this module feeds it the timeline
and pipes the frames into ffmpeg.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import script
from .config import Settings

ASSETS = Path(__file__).parent / "motion_assets"
TYPES = ("kinetic", "burst", "number", "list", "pattern", "ring", "cube", "phone", "route", "world", "icon", "iconrow")
ICON_NAMES = ("rocket", "coin", "bulb", "clock", "heart", "shield", "lock", "cart", "house", "gear", "globe", "star", "growth", "magnifier",
              "person", "check", "phone", "laptop", "cloud", "sun", "tree", "car", "plane", "book", "bolt", "trophy", "fire", "drop", "chat",
              "mail", "camera", "flask", "pin", "users", "battery", "wifi", "chip")
FACT_TYPES = {"number"}


class MotionError(RuntimeError):
    pass


@dataclass
class Beat:
    narration: str
    type: str
    data: dict = field(default_factory=dict)
    theme: int = 0
    dur: float = 0.0
    visual: str = ""  # what the AI says the scene should show: the brief for its custom animation code
    code: str = ""  # AI-written drawing code for this scene, if it passed the checks


def _s(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n].strip()


def _items(v, n: int, each: int = 40) -> list[str]:
    return [t for t in (_s(x, each) for x in (v if isinstance(v, list) else [])) if t][:n]


def _lines(narration: str) -> list[str]:
    """Split a sentence into 2-4 short display lines."""
    words = narration.replace("\n", " ").split()[:12]
    n = 2 if len(words) <= 6 else 3 if len(words) <= 9 else 4
    size = -(-len(words) // n)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [narration[:30]]


def sanitize_beat(raw: dict, index: int = 0) -> Beat | None:
    if not isinstance(raw, dict):
        return None
    narration = _s(raw.get("narration"), 400)
    if not narration:
        return None
    kind = raw.get("type") if raw.get("type") in TYPES else "kinetic"
    d = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    theme = raw.get("theme") if isinstance(raw.get("theme"), int) else index
    visual = _s(raw.get("visual"), 400)
    if kind == "kinetic":
        lines = [t for t in (_s(x, 24) for x in d.get("lines", []) if isinstance(x, (str, int))) if t][:4] if isinstance(d.get("lines"), list) else []
        data = {"lines": lines or _lines(narration), "sub": _s(d.get("sub"), 50)}
        if isinstance(d.get("accent"), int):
            data["accent"] = d["accent"]
    elif kind in ("burst", "pattern", "ring"):
        text = _s(d.get("text"), 28) or _s(narration, 28)
        data = {"text": text, "sub": _s(d.get("sub"), 50)}
    elif kind in ("cube", "world"):
        data = {"text": _s(d.get("text"), 30) or _s(narration, 30)}
    elif kind == "icon":
        icon = d.get("icon") if d.get("icon") in ICON_NAMES else "star"
        data = {"icon": icon, "text": _s(d.get("text"), 26) or _s(narration, 26), "sub": _s(d.get("sub"), 50)}
    elif kind == "iconrow":
        items = []
        for it in d.get("items", []) if isinstance(d.get("items"), list) else []:
            if isinstance(it, dict) and _s(it.get("label"), 18):
                items.append({"icon": it.get("icon") if it.get("icon") in ICON_NAMES else "star", "label": _s(it.get("label"), 18)})
        if len(items) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 24), "items": items[:4]}
    elif kind == "number":
        try:
            value = float(d.get("value"))
        except (TypeError, ValueError):
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"value": int(value) if value == int(value) else round(value, 1), "prefix": _s(d.get("prefix"), 3),
                "suffix": _s(d.get("suffix"), 6), "label": _s(d.get("label"), 40)}
    elif kind == "list":
        items = _items(d.get("items"), 5)
        if len(items) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 24) or "Key points", "items": items}
    elif kind == "phone":
        items = _items(d.get("items"), 4, 28)
        if len(items) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 22) or "App", "items": items, "text": _s(d.get("text"), 26)}
    else:  # route
        points = _items(d.get("points"), 4, 18)
        if len(points) < 2:
            return sanitize_beat({**raw, "type": "kinetic", "data": {}}, index)
        data = {"title": _s(d.get("title"), 26), "points": points}
    return Beat(narration, kind, data, theme, visual=visual)


def parse_storyboard(content: str) -> list[Beat]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    beats = [b for i, s in enumerate(data["scenes"]) if (b := sanitize_beat(s, i))]
    if not beats:
        raise ValueError("empty storyboard")
    return beats


SYSTEM = """You direct short motion-graphics videos in the style of polished explainer and promo animation: bold typography, drawn icons, 3D shapes and app-style scenes. Every scene has narration (spoken aloud) and an animated picture that must show what the narration says, literally and concretely.
Reply with JSON only: {"scenes":[{"narration":"...","visual":"...","type":"...","theme":0,"data":{...}}]}
"visual": one or two vivid sentences describing the picture to animate for this scene: the objects, what moves, what appears in what order (for example "A rocket lifts off from the bottom with a smoke trail while stars drift and a moon glows, the words TO THE MOON drop in at the top"). Be concrete and specific to this narration. Never describe people's faces or realistic photos: use icons, shapes, charts, objects and big words.
"type" and "data" are a simpler built-in version of the same scene, used if the custom animation fails:
- kinetic: {"lines":["2-4 words max","per line","up to 4 lines"],"accent":1,"sub":"optional"} stacked punchy words, "accent" is the index of the line to highlight.
- burst: {"text":"TWO WORDS","sub":"optional"} loud sticker words over a sunburst. Hooks and reveals.
- icon: {"icon":"rocket","text":"SHORT LABEL","sub":"optional"} one big animated drawn icon.
- iconrow: {"title":"3 words","items":[{"icon":"coin","label":"Save"},{"icon":"growth","label":"Invest"}]} 2 to 4 icons with labels.
- number: {"value":85,"prefix":"","suffix":"%","label":"what it measures","fill":0.85} one counting figure.
- list: {"title":"3 words","items":["short","short","short"]}
- phone: {"title":"App","items":["feature","feature","feature"],"text":"optional"}
- route: {"title":"optional","points":["Start","Middle","End"]}
- ring: {"text":"TITLE","sub":"optional"} glowing 3D particle ring. cube: {"text":"TITLE"} turning 3D shape. world: {"text":"TITLE"} growing isometric 3D city. pattern: {"text":"TITLE"} tile pattern.
Icons: rocket, coin, bulb, clock, heart, shield, lock, cart, house, gear, globe, star, growth, magnifier, person, check, phone, laptop, cloud, sun, tree, car, plane, book, bolt, trophy, fire, drop, chat, mail, camera, flask, pin, users, battery, wifi, chip.
"theme" is 0 to 7, a colour palette: 0 cream, 1 midnight, 2 yellow, 3 blue, 4 black and orange, 5 ice, 6 forest, 7 red. Change it between scenes.
Rules:
- Open with a hook scene that grabs attention. Close with a scene that lands the point.
- Vary the scene types and the visuals. Never the same type twice in a row.
- Use numbers and statistics ONLY when you are confident they are real. Never invent figures.
- Plain spoken language, no stage directions, no emojis."""


def llm_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> list[Beat]:
    n = script.scene_count(seconds)
    words = int(seconds * script.WORDS_PER_SECOND)
    user = f"Title: {title}\nTopic: {topic}\nWrite exactly {n} scenes, about {words} words of narration in total."
    if style_hint:
        user += f"\nStyle notes: {style_hint}"
    return parse_storyboard(script.chat(settings, SYSTEM, user))


_ROTATION = ("burst", "icon", "kinetic", "cube", "icon", "kinetic", "ring", "iconrow", "kinetic", "world")


def demo_storyboard(title: str, topic: str, seconds: int) -> list[Beat]:
    """No key: the template sentences become scenes, mixing big drawn icons, stacked type and 3D looks."""
    from . import icons

    lines = [s.narration for s in script.demo_script(title, topic, seconds)]
    mapping = {"coins": "coin", "growth": "growth"}
    beats = []
    for i, line in enumerate(lines):
        kind = _ROTATION[i % len(_ROTATION)]
        guess = icons.guess(f"{line} {title}") or ""
        icon = mapping.get(guess, guess if guess in ICON_NAMES else ("bulb", "globe", "star", "rocket")[i % 4])
        short = " ".join(line.split()[:3])
        if kind == "iconrow":
            words = [w for w in line.replace(",", " ").split() if len(w) > 3][:3] or ["Idea", "Plan", "Result"]
            data = {"title": "", "items": [{"icon": ("bulb", "gear", "growth")[k], "label": w} for k, w in enumerate(words)]}
        elif kind == "icon":
            data = {"icon": icon, "text": short}
        elif kind in ("burst", "cube", "ring", "world", "pattern"):
            data = {"text": short}
        else:
            data = {}
        beats.append(sanitize_beat({"narration": line, "type": kind, "data": data}, i) or Beat(line, "kinetic", {"lines": _lines(line)}, i))
    return beats


def make_storyboard(title: str, topic: str, seconds: int, settings: Settings, style_hint: str = "") -> tuple[list[Beat], list[str]]:
    warnings: list[str] = []
    if settings.live_script:
        try:
            beats = llm_storyboard(title, topic, seconds, settings, style_hint)
            if any(b.type in FACT_TYPES for b in beats):
                warnings.append("Numbers in motion videos are written by the AI. Check them before you publish.")
            return beats, warnings
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", "")
            warnings.append(f"Script writer unavailable, used a template instead ({exc.__class__.__name__} {code}).".replace(" )", ")"))
    else:
        warnings.append("No script key set, used a template script. Add FRIDAY_LLM_API_KEY for real scripts.")
    return demo_storyboard(title, topic, seconds), warnings


# ---------- AI-written scene animation ----------

CODE_SYSTEM = """You are a motion designer who writes the drawing code for one scene of a short video. You write the BODY of a JavaScript function with parameters (g, t, d):
- t = seconds since the scene started, d = the scene's length in seconds (usually 3.5 to 9). The scene is a PURE function of t: draw the whole frame from scratch every call, with no stored state. Use g.ease and g.seg for all motion, and hold the final state once everything has arrived.
- Everything is drawn on the 2D canvas context g.ctx in design units: the short side of the frame is 1080. g.W and g.H are the frame size in those units: either 1080x1920 (portrait) or 1920x1080 (landscape), so lay out relative to g.W and g.H and keep important things inside a 6% margin.
- g.th = {bg, fg, accent, alt, soft, dark} is this scene's colour palette (hex strings). Use it so scenes match. g.PI2 = 2*PI.
Toolkit:
 g.bg(color, color2?)               fill the frame (solid, or vertical gradient). Always do this first.
 g.grad(x0,y0,x1,y1,[c0,c1,...])    a gradient usable as fillStyle
 g.rrect(x,y,w,h,r)                 builds a rounded-rect path (then ctx.fill() / ctx.stroke())
 g.glow(x,y,radius,color,alpha)     soft light blob (additive)
 g.text(str,x,y,size,color,{font:'black'|'bold'|'med'|'serif', align:'center'|'left'|'right', scale, rot, alpha, shadow:color, sd:offset})   centred on x,y
 g.fit(str,font,maxWidth,maxSize)   returns the font size that makes str fit maxWidth
 g.icon(name,x,y,size,{t, flip, rot, shadow})   a drawn, animated icon centred on x,y. Names: rocket coin bulb clock heart shield lock cart house gear globe star growth magnifier person check phone laptop cloud sun tree car plane book bolt trophy fire drop chat mail camera flask pin users battery wifi chip. Pass t so it animates.
 g.grid(t,color,gap,alpha)          drifting dot grid.   g.stars(t,seed,count,color)   twinkling stars.   g.sunburst(t,cx,cy,rays,color)
 g.path(svgPathString)              a Path2D from SVG path data, for your own drawings: ctx.fill(g.path("M10 10 L50 10 ..."))
 g.ease.out/inOut/back/elastic/in (x in 0..1 -> eased 0..1)   g.seg(t,a,b) = progress of t between a and b clamped 0..1   g.lerp(a,b,k)   g.clamp(v,0,1)   g.rng(seed) returns a deterministic random function   g.hex(color,alpha) -> rgba string
 g.project(x,y,z,{rx,ry,f,dz,cx,cy}) simple 3D perspective, returns [screenX,screenY,scale,depth]
Rules:
- Make it look professionally animated: layered backgrounds (gradient, glow, drifting shapes), a clear main subject, staggered entrances with overshoot (ease.back / ease.elastic), continuous gentle idle motion afterwards, and text that pops in. Big, bold, readable text of at most 6 words. Fill the frame: avoid tiny content in a big empty area.
- Show the idea of the narration with drawn things: icons, shapes, charts, arrows, objects built from paths and simple shapes. Write real shapes, not placeholders.
- Use only the toolkit and plain JavaScript (Math, arrays, loops with fixed bounds). No while loops, no document/window/fetch/import, no timers, no Date.now: only t. Keep it under 120 lines and fast (under 3000 shapes per frame).
- Reply with ONLY the function body inside one ```js fenced block."""


def _examples() -> str:
    parts = []
    for name, brief in (("rocket", "A rocket lifts off past a glowing moon; the words TO THE MOON drop in."),
                        ("growth", "Bars rise year by year while a percentage counts up to 100%."),
                        ("compare", "Two cards, Rent and Buy, pop in with icons and ticked points and a VS badge.")):
        parts.append(f"Example brief: {brief}\n```js\n{(ASSETS / 'examples' / f'{name}.js').read_text().strip()}\n```")
    return "\n\n".join(parts)


_DENY = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|import|require|eval|Function|document|window|globalThis|self|localStorage|sessionStorage|"
                   r"navigator|location|Worker|setTimeout|setInterval|requestAnimationFrame|constructor|__proto__|prototype|while|canvas|"
                   r"ownerDocument|defaultView|getPrototypeOf|Reflect|Proxy|Object|parent|top|frames|Date)\b")


def extract_code(reply: str) -> str:
    """Pull the JavaScript out of a model reply and refuse anything that is not plain drawing code."""
    m = re.search(r"```(?:js|javascript)?\s*(.*?)```", reply, re.S)
    code = (m.group(1) if m else reply).strip()
    if not code or len(code) > 12000 or len(code) < 80 or _DENY.search(code) or re.search(r"for\s*\([^)]*;\s*;", code):
        return ""
    return code


def _ask_code(beat: Beat, aspect: str, settings: Settings, problem: str = "") -> str:
    orient = "portrait 1080x1920" if aspect == "9:16" else "landscape 1920x1080"
    user = (f"{_examples()}\n\nNow write the scene.\nFrame: {orient}. Scene length d about {beat.dur:.1f} seconds.\n"
            f"Narration: {beat.narration}\nBrief: {beat.visual or beat.narration}\n"
            f"Palette: bg {THEME_HEX[beat.theme % 8]}.")
    if problem:
        user += f"\nYour previous attempt failed: {problem}. Write a corrected, simpler version."
    return extract_code(script.chat(settings, CODE_SYSTEM, user))


THEME_HEX = ("cream", "midnight", "yellow", "blue", "black with orange", "ice", "forest green", "red")


def add_code(beats: list[Beat], aspect: str, settings: Settings, budget: float = 200.0) -> int:
    """Ask the AI for custom animation code for every scene, in parallel. Returns how many scenes got code."""
    import concurrent.futures as cf
    import time

    start = time.monotonic()

    def one(beat: Beat) -> str:
        if time.monotonic() - start > budget:
            return ""
        try:
            return _ask_code(beat, aspect, settings)
        except Exception:
            return ""

    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for beat, code in zip(beats, pool.map(one, beats)):
            beat.code = code
    return sum(1 for b in beats if b.code)


def repair_code(beats: list[Beat], problems: dict[int, str], aspect: str, settings: Settings) -> None:
    """One more try for scenes whose code failed the dry run; scenes that still fail fall back to the built-in look."""
    import concurrent.futures as cf

    def one(i: int) -> tuple[int, str]:
        try:
            return i, _ask_code(beats[i], aspect, settings, problems[i])
        except Exception:
            return i, ""

    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for i, code in pool.map(one, list(problems)):
            beats[i].code = code


# ---------- browser driver ----------

def check_code(beats: list[Beat], w: int, h: int) -> dict[int, str]:
    """Dry-run every coded scene in the browser. Returns {scene index: what went wrong}."""
    problems: dict[int, str] = {}
    for _ in frames(beats, w, h, report=None, check_only=problems):
        pass
    return problems


def find_chromium() -> str | None:
    env = os.environ.get("FRIDAY_CHROMIUM")
    if env and Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    for pattern in ("chromium-*/chrome-linux*/chrome", "chromium/chrome-linux*/chrome", "chromium"):
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                return str(p)
    return None


def frames(beats: list[Beat], w: int, h: int, fps: int = 30, report: list[str] | None = None, check_only: dict | None = None):
    """Yield one JPEG per frame for the whole timeline."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MotionError("playwright is not installed") from exc
    exe = find_chromium()
    quiet = type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda self, *a: None})
    server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: quiet(*a, directory=str(ASSETS), **k))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    story = {"beats": [{"type": b.type, "data": b.data, "theme": b.theme, "dur": b.dur, "code": b.code} for b in beats]}
    total = max(1, round(sum(b.dur for b in beats) * fps))
    try:
        with sync_playwright() as pw:
            kwargs = {"executable_path": exe} if exe else {}
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"], **kwargs)
            try:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(f"{base}/stage.html")
                page.evaluate("(b) => window.loadFonts(b + '/fonts')", base)
                page.set_default_timeout(90000)
                page.evaluate("([s, w, h]) => window.setup(s, w, h)", [story, w, h])
                checks = page.evaluate("() => window.checkBeats()")
                bad = 0
                for i, c in enumerate(checks):
                    if c and not c["ok"]:
                        bad += 1
                        if check_only is not None:
                            check_only[i] = c["err"][:120]
                        page.evaluate("(i) => window.disableBeat(i)", i)
                        if report is not None:
                            report.append(f"scene {i + 1} animation ({c['err'][:60]})")
                if report is not None:
                    report.append(f"__coded {sum(1 for c in checks if c)} {bad}")
                if check_only is not None:
                    return
                grab = "(t) => { window.renderAt(t); return document.getElementById('c').toDataURL('image/jpeg', 0.92).slice(23); }"
                for n in range(total):
                    yield base64.b64decode(page.evaluate(grab, n / fps))
            finally:
                browser.close()
    except MotionError:
        raise
    except Exception as exc:
        raise MotionError(f"{exc.__class__.__name__}: {str(exc)[:200]}") from exc
    finally:
        server.shutdown()
        server.server_close()
