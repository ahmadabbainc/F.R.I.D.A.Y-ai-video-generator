import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from friday import captions, config, inspire, script  # noqa: E402
from friday.pipeline import Request, generate  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_empty_env_values_fall_back_to_defaults(self):
        # CI passes unset secrets and variables as empty strings.
        keys = ["FRIDAY_LLM_BASE_URL", "FRIDAY_LLM_MODEL", "FRIDAY_LLM_API_KEY", "PEXELS_API_KEY"]
        saved = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ[k] = ""
            s = config.load()
            self.assertEqual(s.llm_base_url, config.Settings().llm_base_url)
            self.assertEqual(s.llm_model, config.Settings().llm_model)
            self.assertEqual(s.mode, "demo")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class ScriptTests(unittest.TestCase):
    def test_parse_scenes_handles_code_fences(self):
        text = '```json\n{"scenes":[{"narration":"Hello there.","keywords":"sun"},{"narration":"  ","keywords":"x"}]}\n```'
        scenes = script.parse_scenes(text)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0].keywords, "sun")

    def test_parse_scenes_rejects_empty(self):
        with self.assertRaises(Exception):
            script.parse_scenes('{"scenes": []}')

    def test_demo_script_respects_length(self):
        scenes = script.demo_script("Save money fast", "Track spending. Cancel extras.", 45)
        self.assertEqual(len(scenes), script.scene_count(45))
        self.assertTrue(all(s.narration for s in scenes))


class CaptionTests(unittest.TestCase):
    def test_chunks_respect_width(self):
        for chunk in captions.chunk_words("one two three four five six seven eight nine ten", 20):
            self.assertLessEqual(len(chunk), 20)

    def test_ass_has_events_and_no_raw_braces(self):
        ass = captions.build_ass([captions.Timed(0, 3, "Use {braces} and \\slashes")], 1080, 1920, "DejaVu Sans")
        self.assertIn("Dialogue:", ass)
        self.assertNotIn("{braces}", ass)


class InspireTests(unittest.TestCase):
    def test_video_id_extraction(self):
        ok = {
            "https://youtu.be/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3": "dQw4w9WgXcQ",
            "https://m.youtube.com/shorts/abcdef12345": "abcdef12345",
        }
        for url, vid in ok.items():
            self.assertEqual(inspire.extract_video_id(url), vid)
        for bad in ["https://example.com/watch?v=abc", "not a url", ""]:
            self.assertIsNone(inspire.extract_video_id(bad))

    def test_analyze_reads_pace_and_hook(self):
        entries = [(i * 3.0, 3.0, "Did you know you can save money fast? Here are five tips for you today.") for i in range(10)]
        profile = inspire.analyze(entries)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.hook, "question")
        self.assertTrue(profile.talks_to_viewer)
        self.assertIn("Open with a question", profile.hint())
        self.assertLessEqual(profile.voice_rate_percent, 25)

    def test_analyze_ignores_short_transcripts(self):
        self.assertIsNone(inspire.analyze([(0.0, 2.0, "too short")]))

    def test_bad_link_is_a_warning_not_a_crash(self):
        profile, warning = inspire.learn_style("https://example.com")
        self.assertIsNone(profile)
        self.assertTrue(warning)


class PipelineTests(unittest.TestCase):
    def test_demo_render_produces_a_playable_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = dataclasses.replace(config.Settings(), render_scale=0.25, data_dir=Path(tmp))
            out = Path(tmp) / "videos" / "t.mp4"
            steps = []
            result = generate(
                Request("Save money fast", "Track every purchase. Cancel unused subscriptions.", "9:16", 20),
                out,
                settings,
                lambda pct, label: steps.append(pct),
            )
            self.assertTrue(out.exists())
            self.assertEqual(steps[-1], 100)
            self.assertEqual(steps, sorted(steps))
            probe = json.loads(
                subprocess.run(
                    ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)],
                    capture_output=True, text=True, check=True,
                ).stdout
            )
            kinds = {s["codec_type"]: s for s in probe["streams"]}
            self.assertEqual(kinds["video"]["codec_name"], "h264")
            self.assertEqual(kinds["audio"]["codec_name"], "aac")
            self.assertEqual((kinds["video"]["width"], kinds["video"]["height"]), (270, 480))
            self.assertGreater(result.duration, 5)
            # the working folder must be cleaned up
            self.assertFalse((out.parent / "t_work").exists())

    def test_wide_format_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = dataclasses.replace(config.Settings(), render_scale=0.25, data_dir=Path(tmp))
            out = Path(tmp) / "w.mp4"
            generate(Request("Wide check", "One short line.", "16:9", 15), out, settings)
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(probe, "480,270")

    def test_empty_title_is_rejected_with_a_plain_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                generate(Request("   "), Path(tmp) / "x.mp4", config.Settings())
            self.assertIn("title", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()


class SceneKeywordTests(unittest.TestCase):
    def test_each_demo_scene_searches_its_own_words(self):
        from friday import script
        scenes = script.demo_script("Save money", "Cancel the subscriptions you never use. Cook at home three nights a week.", 30)
        words = [s.keywords for s in scenes]
        self.assertGreater(len(set(words)), 1)
        self.assertIn("subscriptions", " ".join(words))
        self.assertIn("cook", " ".join(words))
