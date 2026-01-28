import time
import uuid
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from collectors.run_all import run_collectors

router = APIRouter(prefix="/collectors", tags=["collectors"])

ALLOWED_PROVIDERS = {"aws", "azure", "gcp"}
RUNS: Dict[str, dict] = {}


def _run_job(run_id: str, providers: List[str]):
    status = RUNS[run_id]
    status["state"] = "running"
    status["started_at"] = time.time()
    status["sources"] = {provider: {"state": "pending", "entries": 0, "error": None} for provider in providers}
    try:
        run_collectors(selected_providers=providers, status=status)
        status["state"] = "success"
    except Exception as exc:
        status["state"] = "error"
        status["error"] = str(exc)
    finally:
        status["finished_at"] = time.time()


@router.post("/run")
def run_collection(
    background: BackgroundTasks,
    providers: List[str] = Query(default_factory=lambda: ["aws", "azure"]),
):
    normalized = []
    for provider in providers:
        for item in provider.split(","):
            cleaned = item.strip().lower()
            if cleaned:
                normalized.append(cleaned)
    if not normalized:
        raise HTTPException(status_code=400, detail="No providers specified.")
    invalid = [provider for provider in normalized if provider not in ALLOWED_PROVIDERS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported providers: {', '.join(invalid)}")
    run_id = str(uuid.uuid4())
    RUNS[run_id] = {
        "id": run_id,
        "state": "queued",
        "providers": normalized,
        "sources": {provider: {"state": "pending", "entries": 0, "error": None} for provider in normalized},
        "error": None,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
    }
    background.add_task(_run_job, run_id, normalized)
    return {"run_id": run_id, "state": "queued"}


@router.get("/status/{run_id}")
def collection_status(run_id: str):
    status = RUNS.get(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found.")
    return status
