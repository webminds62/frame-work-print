import json
import threading
import time
import uuid
from pathlib import Path

JOBS_PATH = Path(__file__).resolve().parent / "jobs.jsonl"
_LOCK = threading.Lock()
_JOBS = {}


def _load():
    if not JOBS_PATH.exists():
        return
    for line in JOBS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        _JOBS[item["id"]] = item


def _append(job):
    with JOBS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(job, ensure_ascii=False) + "\n")


def _rewrite():
    with JOBS_PATH.open("w", encoding="utf-8") as handle:
        for job in _JOBS.values():
            handle.write(json.dumps(job, ensure_ascii=False) + "\n")


_load()


def create(payload):
    job = {
        "id": str(uuid.uuid4()),
        "status": "queued",
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0,
        "progress_max": 0,
        "error": None,
        "outputs": [],
        "request": payload,
    }
    with _LOCK:
        _JOBS[job["id"]] = job
        _append(job)
    return job


def update(job_id, **fields):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        job.update(fields)
        job["updated_at"] = time.time()
        _JOBS[job_id] = job
        _rewrite()
        return dict(job)


def get(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_jobs(limit=40):
    with _LOCK:
        items = sorted(_JOBS.values(), key=lambda item: item.get("created_at", 0), reverse=True)
        return [dict(item) for item in items[:limit]]


def active():
    with _LOCK:
        return [dict(job) for job in _JOBS.values() if job.get("status") in ("queued", "running")]


def sweep_orphans(reason="Studio restarted before this job finished."):
    changed = []
    with _LOCK:
        for job in _JOBS.values():
            if job.get("status") not in ("queued", "running"):
                continue
            job["status"] = "error"
            job["error"] = reason
            job["updated_at"] = time.time()
            changed.append(dict(job))
        if changed:
            _rewrite()
    return changed


def gallery(limit=40):
    items = []
    for job in list_jobs(limit=200):
        if job.get("status") != "done":
            continue
        for output in job.get("outputs") or []:
            items.append({
                "job_id": job["id"],
                "created_at": job.get("created_at"),
                "prompt": (job.get("request") or {}).get("prompt"),
                "model": (job.get("request") or {}).get("model"),
                "mode": (job.get("request") or {}).get("mode"),
                "camera": (job.get("request") or {}).get("camera"),
                "format": (job.get("request") or {}).get("format"),
                "output": output,
            })
            if len(items) >= limit:
                return items
    return items
