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


if __name__ == "__main__":
    unittest.main()
