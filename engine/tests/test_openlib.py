import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from friday import config, footage, openlib  # noqa: E402
from friday.script import parse_scenes  # noqa: E402
from test_footage import FakeResponse  # noqa: E402


def commons_page(i, licence, mime="video/webm", size=1000, artist="<a href='x'>Jane</a>"):
    return {
        "index": i,
        "imageinfo": [{
            "url": f"https://upload.example/{i}.webm", "mime": mime, "size": size,
            "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": artist}},
        }],
    }


class LicenceTests(unittest.TestCase):
    def test_only_open_licences_pass(self):
        for ok in ("CC0", "Public domain", "PD-USGov-NASA", "CC BY 4.0", "CC-BY-3.0", "cc by 2.0"):
            self.assertTrue(openlib.licence_ok(ok), ok)
        for bad in ("CC BY-SA 4.0", "CC BY-NC 2.0", "CC BY-ND 2.0", "All rights reserved", "", "Fair use"):
            self.assertFalse(openlib.licence_ok(bad), bad)


class SourceTests(unittest.TestCase):
    def test_nasa_prefers_medium_and_skips_originals(self):
        urls = ["http://x/a~orig.mp4", "http://x/a~preview.mp4", "http://x/a~medium.mp4", "http://x/a.srt"]
        self.assertEqual(openlib.pick_nasa_file(urls), "https://x/a~medium.mp4")
        self.assertIsNone(openlib.pick_nasa_file(["http://x/a.jpg"]))

    def test_commons_skips_restricted_wrong_type_and_huge_files(self):
        pages = {str(i): p for i, p in enumerate([
            commons_page(1, "CC BY-SA 4.0"),
            commons_page(2, "CC BY 4.0", mime="image/jpeg"),
            commons_page(3, "CC BY 4.0", size=openlib.MAX_BYTES + 1),
            commons_page(4, "CC BY 4.0"),
        ], 1)}
        with mock.patch.object(openlib, "_get_json", lambda *a, **k: {"query": {"pages": pages}}):
            cid, url, credit = openlib.commons("rocket", True, set())
        self.assertEqual(url, "https://upload.example/4.webm")
        self.assertEqual(credit, "Wikimedia Commons (Jane, CC BY 4.0)")  # HTML stripped

    def test_commons_returns_none_when_nothing_is_licensed(self):
        pages = {"1": commons_page(1, "CC BY-NC 4.0")}
        with mock.patch.object(openlib, "_get_json", lambda *a, **k: {"query": {"pages": pages}}):
            self.assertIsNone(openlib.commons("x", True, set()))

    def test_archive_picks_largest_mp4_under_the_cap(self):
        files = [{"name": "a.mp4", "size": "100"}, {"name": "b.mp4", "size": "900"},
                 {"name": "huge.mp4", "size": str(openlib.MAX_BYTES + 5)}, {"name": "t_thumb.mp4", "size": "50"},
                 {"name": "c.ogv", "size": "999"}]
        self.assertEqual(openlib.pick_archive_file(files), "b.mp4")


class RoutingTests(unittest.TestCase):
    def run_fetch(self, open_sources=True, **kw):
        order = []

        def lib(name):
            def f(q, portrait, used):
                order.append((name, q))
                return (1, f"https://{name}/c.mp4", f"{name} credit")
            return f

        def pixabay(q, portrait, settings, used, **kw):
            order.append(("Pixabay", q))
            return (2, "https://pix/c.mp4")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(footage, "_download", lambda *a, **k: None), \
                mock.patch.dict(openlib.LIBRARIES, {"NASA": lib("NASA"), "Wikimedia Commons": lib("Commons"),
                                                    "Internet Archive": lib("Archive")}, clear=True), \
                mock.patch.object(footage, "_pixabay", pixabay):
            s = dataclasses.replace(config.Settings(), pixabay_api_key="k", open_sources=open_sources)
            result = footage.fetch_clip("rocket launch", "9:16", Path(tmp) / "c.mp4", s, set(), **kw)
        return result, order

    def test_real_scene_tries_open_libraries_first_with_the_named_search(self):
        result, order = self.run_fetch(search="SpaceX Falcon 9 launch", real=True, open_libs=True)
        self.assertEqual(order[0], ("NASA", "SpaceX Falcon 9 launch"))
        self.assertEqual(result[1], "NASA credit")

    def test_generic_scene_uses_stock_first(self):
        result, order = self.run_fetch(open_libs=True)
        self.assertEqual(order, [("Pixabay", "rocket launch")])
        self.assertEqual(result[1], "Pixabay")

    def test_open_sources_switch_off_means_no_library_calls(self):
        _, order = self.run_fetch(open_sources=False, search="SpaceX", real=True, open_libs=True)
        self.assertEqual([n for n, _ in order], ["Pixabay"])

    def test_default_settings_are_offline(self):
        self.assertFalse(config.Settings().open_sources)

    def test_oversize_download_is_refused(self):
        class Big(FakeResponse):
            headers = {"Content-Length": str(openlib.MAX_BYTES + 1)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(footage.requests, "get", lambda *a, **k: Big()):
            with self.assertRaises(ValueError):
                footage._download("https://x/y.mp4", Path(tmp) / "c.mp4", openlib.MAX_BYTES)


class SceneParsingTests(unittest.TestCase):
    def test_kind_and_search_are_read(self):
        scenes = parse_scenes('{"scenes":[{"narration":"A","keywords":"rocket launch","kind":"real","search":"Falcon 9"},'
                              '{"narration":"B","keywords":"city night"}]}')
        self.assertTrue(scenes[0].real)
        self.assertEqual(scenes[0].search, "Falcon 9")
        self.assertFalse(scenes[1].real)


if __name__ == "__main__":
    unittest.main()
