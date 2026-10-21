"""Command line: `python -m friday render --title "..." --topic "..." --out video.mp4`
and `python -m friday serve`."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .pipeline import Request, generate


def main() -> None:
    parser = argparse.ArgumentParser(prog="friday")
    sub = parser.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="make one video")
    r.add_argument("--title", required=True)
    r.add_argument("--topic", default="")
    r.add_argument("--kind", default="footage", choices=["footage", "explainer", "motion"])
    r.add_argument("--aspect", default="9:16", choices=["9:16", "16:9"])
    r.add_argument("--seconds", type=int, default=45)
    r.add_argument("--style-url", default="")
    r.add_argument("--out", default="friday.mp4")
    r.add_argument("--notes", default="", help="write any warnings to this text file")

    s = sub.add_parser("serve", help="run the API")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    settings = config.load()

    if args.cmd == "render":
        result = generate(
            Request(args.title, args.topic, args.aspect, args.seconds, args.style_url, args.kind),
            Path(args.out),
            settings,
            lambda pct, label: print(f"[{pct:3d}%] {label}", flush=True),
        )
        for warning in result.warnings:
            print(f"note: {warning}")
        if args.notes:
            Path(args.notes).write_text("\n".join(result.warnings), encoding="utf-8")
        print(f"Saved {result.video} ({result.duration:.1f}s, {result.scenes} scenes)")
    else:
        import uvicorn

        uvicorn.run("friday.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
