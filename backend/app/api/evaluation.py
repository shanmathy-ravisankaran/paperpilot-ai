from fastapi import APIRouter, HTTPException

from app.api.papers import library
from app.core.config import get_settings
from app.services.evaluation import list_runs, run_retrieval, save_run

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

@router.post("/runs")
def create_run() -> dict:
    try:
        settings = get_settings(); result = run_retrieval(settings, library()); save_run(settings, result); return result
    except (ValueError, FileNotFoundError) as exc: raise HTTPException(422, str(exc)) from exc

@router.get("/runs")
def runs() -> list[dict]: return list_runs(get_settings())

@router.get("/runs/{run_id}")
def run(run_id: str) -> dict:
    found = next((item for item in list_runs(get_settings()) if item["run_id"] == run_id), None)
    if not found: raise HTTPException(404, "Evaluation run not found.")
    return found
