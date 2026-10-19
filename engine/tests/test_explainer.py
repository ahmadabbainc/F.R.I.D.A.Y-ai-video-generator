import dataclasses
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from friday import config, explainer, voice  # noqa: E402
from friday.pipeline import Request, generate  # noqa: E402

voice.PAUSE_SECONDS = 0

try:
    from friday import scenes
except ImportError:  # Pillow or numpy missing
    scenes = None


class SanitizeTests(unittest.TestCase):
    def beat(self, **kw):
        return explainer.sanitize_beat({"narration": "Some narration.", **kw})

    def test_good_scenes_pass_through(self):
        b = self.beat(type="bars", data={"title": "T", "items": [{"label": "A", "value": "12"}, {"label": "B", "value": 30}]})
        self.assertEqual(b.type, "bars")
        self.assertEqual([i["value"] for i in b.data["items"]], [12.0, 30.0])

    def test_bad_data_becomes_a_plain_statement(self):
        cases = [
            dict(type="bars", data={"items": [{"label": "A", "value": 1}]}),                # too few
            dict(type="bars", data={"items": [{"label": "A", "value": "lots"}, {"label": "B", "value": None}]}),
            dict(type="line", data={"points": [{"label": "x", "value": 1}, {"label": "y", "value": 2}]}),
            dict(type="big_number", data={"value": "many"}),
            dict(type="big_number", data={"value": -5}),
            dict(type="timeline", data={"events": [{"when": "2000", "what": "x"}]}),
            dict(type="points", data={"items": ["only one"]}),
            dict(type="hologram", data={}),
            dict(type="bars", data="not a dict"),
            dict(type="bars", data={"items": "nope"}),
        ]
        for kw in cases:
            self.assertEqual(self.beat(**kw).type, "statement", kw)

    def test_numbers_are_parsed_and_junk_is_rejected(self):
        self.assertEqual(explainer._num("$1,200"), 1200.0)
        self.assertEqual(explainer._num("12%"), 12.0)
        self.assertIsNone(explainer._num(True))
        self.assertIsNone(explainer._num(float("nan")))
        self.assertIsNone(explainer._num(1e30))

    def test_text_is_trimmed_and_missing_narration_dropped(self):
        b = self.beat(type="statement", data={"text": "x" * 500})
        self.assertLessEqual(len(b.data["text"]), 130)
        self.assertIsNone(explainer.sanitize_beat({"type": "title"}))
        self.assertIsNone(explainer.sanitize_beat("junk"))

    def test_parse_handles_fenced_json(self):
        raw = "```json\n" + json.dumps({"scenes": [{"narration": "Hi.", "type": "statement", "data": {"text": "Hi"}}]}) + "\n```"
        self.assertEqual(len(explainer.parse_storyboard(raw)), 1)
        with self.assertRaises(Exception):
            explainer.parse_storyboard('{"scenes": []}')


class StoryboardTests(unittest.TestCase):
    def test_no_key_gives_a_template_storyboard_and_says_so(self):
        beats, warns = explainer.make_storyboard("Save money fast", "Track spending. Cancel extras.", 30, config.Settings())
        self.assertEqual(beats[0].type, "title")
        self.assertTrue(all(b.narration for b in beats))
        self.assertTrue(any("No script key" in w for w in warns))

    def test_ai_failure_falls_back_and_ai_numbers_trigger_a_check_note(self):
        s = dataclasses.replace(config.Settings(), llm_api_key="k")
        with mock.patch.object(explainer.script, "chat", side_effect=RuntimeError("down")):
            beats, warns = explainer.make_storyboard("T", "t", 30, s)
        self.assertTrue(beats and any("unavailable" in w for w in warns))
        good = json.dumps({"scenes": [{"narration": "Big.", "type": "big_number", "data": {"value": 5, "label": "x"}}]})
        with mock.patch.object(explainer.script, "chat", return_value=good):
            beats, warns = explainer.make_storyboard("T", "t", 30, s)
        self.assertEqual(beats[0].type, "big_number")
        self.assertTrue(any("Check them" in w for w in warns))


@unittest.skipIf(scenes is None, "Pillow/numpy not installed")
class RenderTests(unittest.TestCase):
    SAMPLES = {
        "title": {"title": "A long title that has to wrap onto more than one line", "subtitle": "sub"},
        "statement": {"text": "He sold his first company for 307 million dollars", "highlight": []},
        "big_number": {"label": "Cars", "value": 1808581, "prefix": "$", "suffix": "M", "caption": "c"},
        "bars": {"title": "T", "items": [{"label": "A", "value": 3}, {"label": "B", "value": 0}], "prefix": "", "suffix": "%"},
        "line": {"title": "T", "points": [{"label": str(i), "value": v} for i, v in enumerate([5, 5, 5, 5])], "prefix": "", "suffix": ""},
        "timeline": {"title": "T", "events": [{"when": "2000", "what": "a" * 80}, {"when": "2001", "what": "b"}]},
        "points": {"title": "T", "items": ["x" * 90, "y"]},
    }

    def test_every_scene_draws_at_both_shapes_and_all_times(self):
        for kind, data in self.SAMPLES.items():
            for w, h in ((216, 384), (384, 216)):
                for t in (0.0, 0.5, 1.5, 3.0, 4.9):
                    img = scenes.render_frame(kind, data, t, 5.0, 0.0, w, h)
                    self.assertEqual(img.size, (w, h), kind)

    def test_frames_are_raw_rgb_of_the_right_size_and_count(self):
        frames = list(scenes.render_frames("statement", self.SAMPLES["statement"], 1.0, 0.0, 108, 192))
        self.assertEqual(len(frames), 30)
        self.assertEqual(len(frames[0]), 108 * 192 * 3)

    def test_animation_actually_moves(self):
        a = scenes.render_frame("bars", self.SAMPLES["bars"], 0.2, 5.0, 0.0, 216, 384).tobytes()
        b = scenes.render_frame("bars", self.SAMPLES["bars"], 2.5, 5.0, 0.0, 216, 384).tobytes()
        self.assertNotEqual(a, b)

    def test_number_formatting(self):
        self.assertEqual(scenes.number_text(1808581, 0, "$", "M"), "$1,808,581M")
        self.assertEqual(scenes.decimals_of(2.5), 1)
        self.assertEqual(scenes.decimals_of(3.0), 0)


@unittest.skipIf(scenes is None, "Pillow/numpy not installed")
class ExplainerVideoTests(unittest.TestCase):
    def test_demo_explainer_renders_a_playable_video_with_matching_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = dataclasses.replace(config.Settings(), render_scale=0.2, data_dir=Path(tmp))
            out = Path(tmp) / "v.mp4"
            r = generate(Request("Save money fast", "Track spending. Cancel extras. Cook at home.", "9:16", 15, "", "explainer"), out, s)
            self.assertGreater(out.stat().st_size, 1000)
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "csv=p=0", str(out)],
                                  capture_output=True, text=True).stdout
            self.assertIn("h264", info)
            self.assertIn("aac", info)
            self.assertAlmostEqual(voice.probe_duration(out), r.duration, delta=0.4)
            self.assertFalse((Path(tmp) / "v_work").exists())  # temp files cleaned up

    def test_one_broken_scene_falls_back_to_plain_text_instead_of_failing(self):
        calls = {"n": 0}
        real = scenes.render_frames

        def flaky(kind, *a, **k):
            calls["n"] += 1
            if kind == "title":
                raise RuntimeError("boom")
            return real(kind, *a, **k)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(scenes, "render_frames", flaky):
            s = dataclasses.replace(config.Settings(), render_scale=0.2, data_dir=Path(tmp))
            out = Path(tmp) / "v.mp4"
            generate(Request("Hello world", "One. Two.", "16:9", 15, "", "explainer"), out, s)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
