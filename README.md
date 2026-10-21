# Friday

Give Friday a title and press **Generate**. It writes the script, finds footage, records the voice, burns in captions and hands you a finished video.

It runs as a website, installs on Android and iPhone from the browser, and works on desktop. The renders happen on GitHub for free, so nothing runs on your own device.

## How it works

```
Browser app (GitHub Pages)  ──starts──▶  Render workflow (GitHub Actions)
        ▲                                        │
        └────── watches progress, plays ◀────────┘  publishes the mp4 as a release
```

- `web/` is the app: plain HTML, CSS and JavaScript, no build step. It installs as a PWA.
- `engine/` is the video maker (Python and ffmpeg): script, footage, voice, captions, render.
- `.github/workflows/render.yml` runs the engine when the app asks.
- Optional: run the engine as a server yourself (`engine/Dockerfile`) and point the app at it.

## Set up (about 10 minutes, no cost)

1. **Turn on the app.** In this repository: Settings → Pages → Source: **GitHub Actions**. Push to `main` and the app appears at `https://<your-name>.github.io/<repository>/`.
2. **Add free keys** (Settings → Secrets and variables → Actions). Friday works without them, using template scripts and plain backgrounds, but real results need these:
   - `PIXABAY_API_KEY` (secret): free stock footage. Sign up at pixabay.com, then open pixabay.com/api/docs/ while logged in and your key is shown on the page. Friday credits Pixabay in the video's notes, as their API terms ask.
   - `PEXELS_API_KEY` (secret, optional alternative): Pexels paused new API keys in October 2026, but existing keys still work and Friday uses them first if both are set.
   - `FRIDAY_LLM_API_KEY` (secret): any OpenAI-compatible chat key. The default endpoint is Google's Gemini (Google AI Studio has a free key). To use another provider, set the variables `FRIDAY_LLM_BASE_URL` and `FRIDAY_LLM_MODEL`. Free-tier limits and model names change, so check them if scripts stop working.
3. **Make a token** at github.com/settings/personal-access-tokens/new: *Only select repositories*, pick this one, set **Actions: Read and write**, nothing else. It can do nothing except start renders on this repository.
4. **Open the app**, tap the gear, paste the token. The token stays in your browser only.
5. **Install it.** Android: browser menu → Install app. iPhone: Safari → Share → Add to Home Screen. Desktop: the install icon in Chrome or Edge.

## Using it

Type a title, press **Generate video**. The topic is optional; leave it empty and Friday decides what to cover. Pick vertical or wide, and 30, 45 or 60 seconds.

**Match a video's style** is optional. Paste a YouTube link and Friday reads its captions to learn the pace, sentence length and how it opens, then writes in that shape. It never reuses the words. If the video has no captions, Friday says so and carries on.

A video takes a few minutes. You can close the page while it renders; reopen it and it picks up the same job. Finished videos are published as releases on this repository (the newest 20 are kept).

## Two kinds of video

Pick the type before you press Generate:

- **Footage**: real video clips matched to each line (stock and openly licensed libraries, below).
- **Animated**: motion graphics drawn entirely by code, with no stock footage, so the pictures always match the voice. The AI writes a storyboard and Friday animates it: a rocket that flies, coins that drop, gears that turn, a spinning globe, a beating heart and other animated icons; flow diagrams with pulses of light travelling between steps; side-by-side comparisons; concept maps with ideas orbiting a centre; kinetic text; counting numbers; bar and line charts; timelines. There are drifting particles, a slow camera push-in and colour-swipe transitions. Scenes are never shorter than about three and a half seconds, so every animation finishes.
- **Motion**: bold kinetic typography on colour fields, sticker-style burst words, counting numbers, check lists, animated tile patterns, a glowing 3D particle ring, a turning 3D shape, a phone showing app cards, an animated route map and an isometric 3D city that grows while the camera orbits. Drawn in a headless Chromium (on GitHub Actions the runner's Chrome is used) with bundled open fonts (Inter, Lora; SIL OFL), wipe transitions between scenes, captions burned in. It aims at the look of code-made promo and explainer motion graphics, not at hand-built per-video animation.

The AI writes any numbers, dates or statistics in animated videos, and Friday adds a note to check them before you publish. Without a script key, animated videos use simple text scenes only.

## Footage sources

Friday searches several places for each scene and only keeps clips it is allowed to reuse:

- **Stock** (Pixabay, and Pexels if you have a key) for everyday scenes.
- **Openly licensed libraries**, no key needed: NASA, Wikimedia Commons and the Internet Archive. For scenes about a specific real event or place Friday tries these first. Only public domain, CC0 and CC BY clips are used (never NC, ND or SA), and each clip's author and licence are listed in the video's notes. Set the variable `FRIDAY_OPEN_SOURCES` to `0` to turn them off.

Friday does not download from YouTube, Reddit or other sites whose content belongs to the people who posted it.

## Things to know

- **Videos are public.** Releases on a public repository can be opened by anyone with the link. Don't generate anything private. A private repository would hide them but GitHub Pages then needs a paid plan.
- **Free limits.** GitHub's standard runners are free on public repositories. Pages has a soft bandwidth limit of 100 GB a month. Both can change.
- **Stock footage and music rights** follow each provider's license. Check them before publishing commercially.
- **No App Store build.** iPhone support is the installable web app. A native iOS app needs a paid Apple developer account.

## Status

Checked so far: the engine renders real H.264 and AAC video in demo mode (title, captions, both formats); the script, captions and style-learning logic have tests; the app was exercised in a browser against a simulated GitHub API at phone and desktop sizes, including failures and resuming.

Not yet checked against the real services: the NASA, Wikimedia Commons and Internet Archive lookups (tested with simulated responses only), the animated type on a real GitHub run, and YouTube caption fetching. The CI workflow runs the engine tests (including the API server) on every push.

## Run it locally

```bash
cd engine
pip install -r requirements.txt
python -m friday render --title "How to save money" --out video.mp4
python -m friday serve        # optional HTTP engine on :8000
python -m unittest discover -s tests
```

Needs Python 3.11+ and ffmpeg.

## Credits

Inspired by [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (MIT). Friday is a fresh, much smaller codebase. Inter typeface by the Inter Project Authors (OFL).

MIT licensed.
