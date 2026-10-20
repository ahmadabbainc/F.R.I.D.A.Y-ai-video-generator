import dataclasses
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from friday import config, footage, voice  # noqa: E402

voice.PAUSE_SECONDS = 0
from friday.pipeline import Request, generate  # noqa: E402


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self._data, self._content = data, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._data

    def iter_content(self, chunk_size=0):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def vid(w, h, url=None):
    return {"url": url or f"https://cdn.example/{w}x{h}.mp4", "width": w, "height": h, "size": 1}


PIXABAY = {
    "hits": [
        {"id": 1, "videos": {"large": vid(3840, 2160), "medium": vid(1920, 1080, "https://cdn.example/land1.mp4")}},
        {"id": 2, "videos": {"large": {"url": "", "width": 0, "height": 0}, "medium": vid(1080, 1920, "https://cdn.example/port2.mp4")}},
        {"id": 3, "videos": {"medium": {"url": ""}, "small": {"url": ""}}},  # nothing usable
        {"id": 5, "tags": "cooking, kitchen, dinner", "videos": {"medium": vid(1920, 1080, "https://cdn.example/tagged5.mp4")}},
        {"id": 4, "videos": {"medium": vid(1080, 1920, "https://cdn.example/port4.mp4")}},
    ]
}


def make_sample_clip() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "c.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:d=1:r=30",
             "-pix_fmt", "yuv420p", str(out)],
            check=True,
        )
        return out.read_bytes()


def fake_network(pixabay=PIXABAY, clip=b"x", fail_pexels=False, fail_all=False):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if fail_all:
            raise ConnectionError("down")
        if "pexels" in url:
            if fail_pexels:
                raise ConnectionError("pexels down")
            return FakeResponse({"videos": []})
        if "pixabay.com/api" in url:
            return FakeResponse(pixabay)
        return FakeResponse(content=clip)  # a clip download

    return get, calls


class FootageTests(unittest.TestCase):
    def settings(self, **kw):
        return dataclasses.replace(config.Settings(), **kw)

    def run_fetch(self, aspect="9:16", used=None, **kw):
        get, calls = fake_network(**kw.pop("net", {}))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            used = set() if used is None else used
            result = footage.fetch_clip("saving money", aspect, Path(tmp) / "c.mp4", self.settings(**kw), used)
            return result, calls, used

    def test_no_keys_means_no_network_calls(self):
        result, calls, _ = self.run_fetch()
        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_blank_keywords_are_skipped(self):
        get, calls = fake_network()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            r = footage.fetch_clip("  ", "9:16", Path(tmp) / "c.mp4", self.settings(pixabay_api_key="k"), set())
        self.assertIsNone(r)
        self.assertEqual(calls, [])

    def test_pixabay_prefers_portrait_for_vertical_videos(self):
        result, calls, used = self.run_fetch(pixabay_api_key="k")
        self.assertEqual(result[1], "Pixabay")
        self.assertIn("https://cdn.example/port2.mp4", calls)  # first portrait hit, not the landscape one
        self.assertEqual(used, {("Pixabay", 2)})

    def test_pixabay_prefers_landscape_for_wide_videos(self):
        _, calls, used = self.run_fetch(aspect="16:9", pixabay_api_key="k")
        self.assertIn("https://cdn.example/land1.mp4", calls)
        self.assertEqual(used, {("Pixabay", 1)})

    def test_used_clips_are_not_repeated(self):
        _, calls, used = self.run_fetch(pixabay_api_key="k", used={("Pixabay", 2)})
        self.assertIn("https://cdn.example/port4.mp4", calls)
        self.assertIn(("Pixabay", 4), used)

    def test_medium_is_chosen_over_4k(self):
        self.assertEqual(footage._pick_pixabay_file({"large": vid(3840, 2160), "medium": vid(1920, 1080)})[0], "https://cdn.example/1920x1080.mp4")
        self.assertIsNone(footage._pick_pixabay_file({"medium": {"url": ""}}))

    def test_falls_through_to_the_next_provider(self):
        result, _, _ = self.run_fetch(pexels_api_key="p", pixabay_api_key="k", net={"fail_pexels": True})
        self.assertEqual(result[1], "Pixabay")

    def test_total_failure_returns_none_instead_of_raising(self):
        result, _, used = self.run_fetch(pexels_api_key="p", pixabay_api_key="k", net={"fail_all": True})
        self.assertIsNone(result)
        self.assertEqual(used, set())

    def test_key_is_sent_as_a_parameter_not_logged_in_the_url(self):
        seen = {}

        def get(url, **kw):
            seen["params"] = kw.get("params")
            return FakeResponse({"hits": []})

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            footage.fetch_clip("x", "9:16", Path(tmp) / "c.mp4", self.settings(pixabay_api_key="SECRET"), set())
        self.assertEqual(seen["params"]["key"], "SECRET")
        self.assertEqual(seen["params"]["safesearch"], "true")


class PipelineFootageTests(unittest.TestCase):
    def render(self, **net):
        clip = make_sample_clip()
        get, _ = fake_network(clip=clip, **net)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            settings = dataclasses.replace(config.Settings(), render_scale=0.25, data_dir=Path(tmp), pixabay_api_key="k")
            out = Path(tmp) / "v.mp4"
            result = generate(Request("Save money fast", "Track spending. Cancel extras.", "9:16", 15), out, settings)
            self.assertTrue(out.exists() and out.stat().st_size > 1000)
            return result.warnings

    def test_stock_footage_is_used_and_credited(self):
        notes = self.render()
        self.assertIn("Footage from Pixabay.", notes)
        self.assertFalse([n for n in notes if "Couldn't fetch stock footage" in n], notes)

    def test_key_set_but_every_download_fails_is_reported(self):
        notes = self.render(fail_all=True)
        self.assertTrue([n for n in notes if "Couldn't fetch stock footage" in n], notes)
        self.assertNotIn("Footage from Pixabay.", notes)


if __name__ == "__main__":
    unittest.main()


class TagRelevanceTests(unittest.TestCase):
    def test_clip_tagged_with_the_scene_words_wins(self):
        get, calls = fake_network()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            s = dataclasses.replace(config.Settings(), pixabay_api_key="k")
            r = footage.fetch_clip("cooking dinner", "9:16", Path(tmp) / "c.mp4", s, set())
        self.assertEqual(r[1], "Pixabay")
        self.assertIn("https://cdn.example/tagged5.mp4", calls)


class ClipLengthTests(unittest.TestCase):
    def test_clips_long_enough_for_the_scene_are_preferred(self):
        hits = {"hits": [
            {"id": 1, "duration": 3, "videos": {"medium": vid(1080, 1920, "https://cdn.example/short.mp4")}},
            {"id": 2, "duration": 12, "videos": {"medium": vid(1080, 1920, "https://cdn.example/long.mp4")}},
        ]}
        get, calls = fake_network(pixabay=hits)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            s = dataclasses.replace(config.Settings(), pixabay_api_key="k")
            footage.fetch_clip("x", "9:16", Path(tmp) / "c.mp4", s, set(), min_seconds=6.0)
        self.assertIn("https://cdn.example/long.mp4", calls)
        self.assertNotIn("https://cdn.example/short.mp4", calls)

    def test_a_short_clip_is_still_used_when_nothing_longer_exists(self):
        hits = {"hits": [{"id": 1, "duration": 3, "videos": {"medium": vid(1080, 1920, "https://cdn.example/short.mp4")}}]}
        get, calls = fake_network(pixabay=hits)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", get):
            s = dataclasses.replace(config.Settings(), pixabay_api_key="k")
            r = footage.fetch_clip("x", "9:16", Path(tmp) / "c.mp4", s, set(), min_seconds=6.0)
        self.assertIsNotNone(r)
