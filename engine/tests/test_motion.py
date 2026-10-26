import json
import unittest

from friday import motion


class SanitizeTests(unittest.TestCase):
    def test_unknown_type_becomes_kinetic(self):
        b = motion.sanitize_beat({"narration": "Money is just an idea people share", "type": "weird"})
        self.assertEqual(b.type, "kinetic")
        self.assertTrue(b.data["lines"])

    def test_bad_number_and_short_list_fall_back(self):
        self.assertEqual(motion.sanitize_beat({"narration": "x y", "type": "number", "data": {"value": "lots"}}).type, "kinetic")
        self.assertEqual(motion.sanitize_beat({"narration": "x y", "type": "list", "data": {"items": ["one"]}}).type, "kinetic")
        self.assertEqual(motion.sanitize_beat({"narration": "x y", "type": "route", "data": {"points": ["a"]}}).type, "kinetic")

    def test_empty_narration_rejected_and_text_clipped(self):
        self.assertIsNone(motion.sanitize_beat({"narration": "", "type": "kinetic"}))
        b = motion.sanitize_beat({"narration": "hi there", "type": "burst", "data": {"text": "x" * 100}})
        self.assertLessEqual(len(b.data["text"]), 28)

    def test_parse_storyboard_fenced(self):
        raw = "```json\n" + json.dumps({"scenes": [{"narration": "Hello world", "type": "ring", "data": {"text": "Hi"}}]}) + "\n```"
        self.assertEqual(motion.parse_storyboard(raw)[0].type, "ring")
        with self.assertRaises(Exception):
            motion.parse_storyboard('{"scenes": []}')

    def test_demo_storyboard(self):
        beats = motion.demo_storyboard("Why cats purr", "", 30)
        self.assertGreaterEqual(len(beats), 3)
        self.assertTrue(all(b.type in motion.TYPES for b in beats))


class CodeSceneTests(unittest.TestCase):
    def test_extract_code_filters_unsafe(self):
        ok = "g.bg(g.th.bg);\n" + "g.text('Hello', g.W/2, g.H/2, 120, g.th.fg);\n" * 4
        self.assertTrue(motion.extract_code("```js\n" + ok + "```"))
        for bad in ("fetch('http://x')", "document.body", "while (true) {}", "for (;;) {}", "for (let i=0;;i++) {}", "g.ctx.canvas.ownerDocument", "Date.now()"):
            self.assertEqual(motion.extract_code("```js\n" + ok + bad + "\n```"), "", bad)
        self.assertEqual(motion.extract_code("```js\ng.bg()\n```"), "")  # too short to be a real scene

    def test_icon_scene_types_are_sanitized(self):
        b = motion.sanitize_beat({"narration": "Save money", "type": "icon", "data": {"icon": "nonsense", "text": "Save"}, "visual": "a coin"})
        self.assertEqual((b.type, b.data["icon"], b.visual), ("icon", "star", "a coin"))
        row = motion.sanitize_beat({"narration": "Three steps", "type": "iconrow", "data": {"items": [{"icon": "coin", "label": "Save"}]}})
        self.assertEqual(row.type, "kinetic")  # needs at least two items

    def test_add_code_uses_ai_and_survives_failures(self):
        beats = [motion.Beat("A rocket flies", "kinetic", {"lines": ["x"]}, 0, dur=4.0, visual="rocket"), motion.Beat("Second", "kinetic", {"lines": ["y"]}, 1, dur=4.0)]
        good = "```js\n" + (motion.ASSETS / "examples" / "rocket.js").read_text() + "\n```"
        calls = []

        def fake(settings, system, user):
            calls.append(user)
            if "Second" in user:
                raise RuntimeError("quota")
            return good

        from unittest import mock
        with mock.patch.object(motion.script, "chat", fake):
            n = motion.add_code(beats, "9:16", None)
        self.assertEqual(n, 1)
        self.assertTrue(beats[0].code)
        self.assertEqual(beats[1].code, "")


@unittest.skipUnless(motion.find_chromium(), "no browser available")
class BrowserTests(unittest.TestCase):
    def test_dry_run_catches_bad_scenes_and_keeps_good_ones(self):
        good = (motion.ASSETS / "examples" / "growth.js").read_text()
        cases = {
            "good": good,
            "throws": "g.bg(g.th.bg);\nconst a = null;\na.boom();\n" + "// padding to be long enough\n" * 5,
            "blank": "g.bg(g.th.bg);\n" + "// nothing is drawn here at all, padding padding\n" * 4,
            "static": "g.bg(g.th.bg);\ng.text('STILL', g.W/2, g.H/2, 200, g.th.fg);\n" + "// padding to be long enough\n" * 4,
        }
        beats = []
        for i, code in enumerate(cases.values()):
            b = motion.Beat("x", "kinetic", {"lines": ["fallback"]}, i, dur=3.0)
            b.code = code
            beats.append(b)
        problems = motion.check_code(beats, 270, 480)
        self.assertEqual(sorted(problems), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
