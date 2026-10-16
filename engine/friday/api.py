"""HTTP API: create a job, poll it, download the video."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, config
from .pipeline import Request, generate

settings = config.load()
app = FastAPI(title="Friday", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# One render at a time on free hardware; extra jobs wait in line.
pool = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
MAX_KEPT = 30


@dataclass
class Job:
    id: str
    title: str
    status: str = "queued"  # queued | running | done | failed
    progress: int = 0
    label: str = "Waiting in line"
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0


jobs: dict[str, Job] = {}


def require_key(x_friday_key: str = Header(default="")) -> None:
    if settings.access_key and x_friday_key != settings.access_key:
        raise HTTPException(401, "Wrong or missing access key.")


class NewJob(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    topic: str = Field(default="", max_length=2000)
    aspect: str = "9:16"
    seconds: int = Field(default=45, ge=15, le=90)
    style_url: str = Field(default="", max_length=300)


def _video_path(job_id: str):
    return settings.data_dir / "videos" / f"{job_id}.mp4"


def _run(job: Job, body: NewJob) -> None:
    def progress(pct: int, label: str) -> None:
        job.progress, job.label = pct, label

    job.status = "running"
    try:
        result = generate(
            Request(body.title, body.topic, body.aspect, body.seconds, body.style_url),
            _video_path(job.id),
            settings,
            progress,
        )
        job.warnings, job.duration = result.warnings, result.duration
        job.status, job.progress, job.label = "done", 100, "Your video is ready"
    except Exception as exc:
        job.status, job.error = "failed", str(exc) or exc.__class__.__name__
        job.label = "Something went wrong"


def _trim() -> None:
    while len(jobs) > MAX_KEPT:
        oldest = next(iter(jobs))
        _video_path(oldest).unlink(missing_ok=True)
        jobs.pop(oldest, None)


@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "mode": settings.mode, "locked": bool(settings.access_key)}


@app.post("/api/jobs", status_code=202, dependencies=[Depends(require_key)])
def create_job(body: NewJob):
    job = Job(id=uuid.uuid4().hex[:12], title=body.title.strip())
    with lock:
        jobs[job.id] = job
        _trim()
    pool.submit(_run, job, body)
    return job


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_key)])
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "That job no longer exists. Start a new one.")
    return job


@app.get("/api/jobs/{job_id}/video")
def get_video(job_id: str, key: str = "", x_friday_key: str = Header(default="")):
    # Video tags can't send headers, so the key is also accepted as ?key=
    if settings.access_key and settings.access_key not in (key, x_friday_key):
        raise HTTPException(401, "Wrong or missing access key.")
    job = jobs.get(job_id)
    path = _video_path(job_id)
    if not job or job.status != "done" or not path.exists():
        raise HTTPException(404, "Video not ready.")
    name = "".join(c if c.isalnum() or c in "-_ " else "" for c in job.title).strip() or "friday"
    return FileResponse(path, media_type="video/mp4", filename=f"{name}.mp4")
