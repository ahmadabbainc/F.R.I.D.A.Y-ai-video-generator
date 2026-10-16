import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401

    HAVE_API = True
except ImportError:
    HAVE_API = False


@unittest.skipUnless(HAVE_API, "fastapi and httpx are not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["FRIDAY_DATA_DIR"] = cls.tmp.name
        os.environ["FRIDAY_RENDER_SCALE"] = "0.25"
        os.environ["FRIDAY_ACCESS_KEY"] = "secret"
        from fastapi.testclient import TestClient

        from friday import api

        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        for k in ("FRIDAY_DATA_DIR", "FRIDAY_RENDER_SCALE", "FRIDAY_ACCESS_KEY"):
            os.environ.pop(k, None)
        cls.tmp.cleanup()

    H = {"X-Friday-Key": "secret"}

    def test_health_is_open(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["locked"])

    def test_jobs_need_the_key(self):
        r = self.client.post("/api/jobs", json={"title": "x"})
        self.assertEqual(r.status_code, 401)

    def test_empty_title_is_rejected(self):
        r = self.client.post("/api/jobs", json={"title": ""}, headers=self.H)
        self.assertEqual(r.status_code, 422)

    def test_unknown_job_gives_a_helpful_404(self):
        r = self.client.get("/api/jobs/nope", headers=self.H)
        self.assertEqual(r.status_code, 404)
        self.assertIn("Start a new one", r.json()["detail"])

    def test_full_job_lifecycle(self):
        r = self.client.post(
            "/api/jobs",
            json={"title": "API check", "topic": "One line. Two lines.", "seconds": 15},
            headers=self.H,
        )
        self.assertEqual(r.status_code, 202)
        job_id = r.json()["id"]

        deadline = time.time() + 90
        job = {}
        while time.time() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}", headers=self.H).json()
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.5)
        self.assertEqual(job["status"], "done", job)

        # video endpoint accepts the key as a query string for <video> tags
        self.assertEqual(self.client.get(f"/api/jobs/{job_id}/video").status_code, 401)
        v = self.client.get(f"/api/jobs/{job_id}/video?key=secret")
        self.assertEqual(v.status_code, 200)
        self.assertEqual(v.headers["content-type"], "video/mp4")
        self.assertGreater(len(v.content), 1000)


if __name__ == "__main__":
    unittest.main()
