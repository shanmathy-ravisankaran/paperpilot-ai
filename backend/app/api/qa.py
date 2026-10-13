from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.papers import library
from app.core.config import get_settings
from app.services.grounding import GroundedService, GroundingError
from app.services.llm import LlmClient, LlmError, LlmTimeoutError, LlmUnavailableError

router = APIRouter(prefix="/qa", tags=["grounded Q&A"])

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    paper_id: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=6, ge=1, le=12)
class Citation(BaseModel):
    citation_id: str; chunk_id: str; paper_id: str; title: str; page: int; section: str; text: str; score: float
class AskResponse(BaseModel):
    answer: str; citations: list[str]; sources: list[Citation]
class SummarySection(BaseModel):
    text: str; citations: list[str]; not_stated: bool
class SummaryResponse(BaseModel):
    sections: dict[str, SummarySection]; sources: list[Citation]

@lru_cache
def grounded() -> GroundedService:
    return GroundedService(LlmClient(get_settings()))

def _safe(call):
    try: return call()
    except LlmTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LlmUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LlmError, GroundingError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    passages = library().search(request.question, request.top_k, request.paper_id)
    return _safe(lambda: grounded().answer(request.question, passages))

@router.post("/papers/{paper_id}/summary", response_model=SummaryResponse)
def summarize(paper_id: str) -> dict:
    if not library().paper(paper_id):
        raise HTTPException(status_code=404, detail="Paper not found.")
    # Broad query deliberately retrieves representative passages across the selected paper.
    passages = library().search("objective methodology findings limitations contributions", 12, paper_id)
    return _safe(lambda: grounded().summary(passages))
