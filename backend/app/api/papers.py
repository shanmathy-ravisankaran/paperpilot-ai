from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.library import LocalLibrary
from app.services.pdf import PdfValidationError, extract_pdf, validate_pdf

router = APIRouter(prefix="/papers", tags=["papers"])

class Paper(BaseModel):
    id: str; title: str; author: str | None = None; filename: str; page_count: int; chunk_count: int; indexed_at: str
class Passage(BaseModel):
    text: str; score: float; paper_id: str; title: str; page: int; section: str; chunk_id: str
class SearchResponse(BaseModel):
    query: str; results: list[Passage]

@lru_cache
def library() -> LocalLibrary:
    settings = get_settings()
    return LocalLibrary(settings.data_dir, settings.embedding_model)

@router.post("/upload", response_model=Paper, status_code=status.HTTP_201_CREATED)
async def upload_paper(file: Annotated[UploadFile, File(description="A text-based PDF")]) -> dict:
    settings = get_settings()
    data = await file.read()
    try:
        validate_pdf(file.filename, file.content_type, data, settings.max_upload_mb * 1024 * 1024)
        return library().index(file.filename or "paper.pdf", data, extract_pdf(data, file.filename or "paper.pdf"))
    except (PdfValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/search", response_model=SearchResponse)
def search_passages(query: Annotated[str, Query(min_length=2, max_length=500)], top_k: Annotated[int, Query(ge=1, le=20)] = 5) -> SearchResponse:
    return SearchResponse(query=query, results=library().search(query, top_k))

@router.get("", response_model=list[Paper])
def list_papers() -> list[dict]:
    return library().list_papers()

@router.get("/{paper_id}", response_model=Paper)
def get_paper(paper_id: str) -> dict:
    paper = library().paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return paper
