from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.papers import library
from app.api.qa import _safe, grounded
from app.services.research import ResearchService

router = APIRouter(prefix="/research", tags=["cross-paper research"])

DIMENSION_QUERIES = {
    "objective": "abstract purpose of the study study investigated research objective aim",
    "research_questions": "research questions hypotheses research question",
    "methodology": "research design methodology methods study design",
    "sample_population": "participants sample population subjects interviewees demographic",
    "data_collection": "data collection interview survey instrument gathered data",
    "analysis_approach": "data analysis qualitative quantitative statistical analysis coding themes",
    "key_findings": "results findings demonstrated revealed showed",
    "limitations": "limitations of the study limitation constraints future research interview conducted only once",
    "contributions": "contribution implications recommendations significance",
}

def _explicit_dimensions(passage: dict) -> list[str]:
    """High-precision lexical cues supplement semantic retrieval for factual fields."""
    text, section = passage["text"].lower(), passage["section"].lower()
    found: list[str] = []
    if "abstract" in section or "purpose of the study" in text or "purpose statement" in text or (passage["page"] <= 2 and "investigated" in text): found.append("objective")
    if "research question" in text or "research questions" in section: found.append("research_questions")
    if "limitations" in section or "limitation of the study" in text or "conducted only once" in text: found.append("limitations")
    if ("findings" in section or "results" in section) and "descriptive statistics" not in section: found.append("key_findings")
    if "semi-structured interview" in text or "research design" in section: found.append("methodology")
    if "data were gathered" in text or "data collection" in section: found.append("data_collection")
    if "qualitative" in text or "analysis of variance" in text or "chi-square" in text: found.append("analysis_approach")
    if "participants" in text or "sample consisted" in text or "population and sample" in section: found.append("sample_population")
    # Contributions need an actual substantive claim, never a heading, outline, or recommendations alone.
    if "contribution" in text and ("results" in text or "findings" in text) and "references" not in section: found.append("contributions")
    return found

class ResearchRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=2, max_length=5)
class Citation(BaseModel):
    citation_id: str; chunk_id: str; paper_id: str; title: str; page: int; section: str; text: str; score: float

def _paper_evidence(paper_id: str) -> list[dict]:
    """Dimension-aware, bounded evidence selection without claiming full-paper coverage."""
    selected: dict[str, dict] = {}
    for dimension, query in DIMENSION_QUERIES.items():
        for passage in library().search(query, 2, paper_id):
            text = passage["text"].strip()
            section = passage["section"].lower()
            if len(text) < 100 or "references" in section or "bibliography" in section or "table of contents" in section:
                continue
            # Discussion recommendations do not establish a study objective when an abstract/front matter is available.
            if dimension == "objective" and passage["page"] > 2 and "abstract" not in section and "purpose of the study" not in text.lower() and "purpose statement" not in text.lower():
                continue
            if dimension == "research_questions" and "research question" not in text.lower() and "hypoth" not in text.lower():
                continue
            if dimension == "key_findings" and ("descriptive statistics" in section or ("results" not in section and "findings" not in section)):
                continue
            if dimension == "contributions" and "contribution" not in text.lower():
                continue
            entry = selected.setdefault(passage["chunk_id"], {**passage, "dimensions": []})
            entry["dimensions"].append(dimension)
    # Include explicit, high-precision passages from the already indexed paper.
    for passage in library().passages_for_paper(paper_id):
        dimensions = _explicit_dimensions(passage)
        if not dimensions or len(passage["text"].strip()) < 100 or "table of contents" in passage["section"].lower():
            continue
        entry = selected.setdefault(passage["chunk_id"], {**passage, "dimensions": []})
        for dimension in dimensions:
            if dimension not in entry["dimensions"]:
                entry["dimensions"].append(dimension)
    # Reserve one best passage for each factual dimension before filling remaining budget.
    ranked = sorted(selected.values(), key=lambda item: (-len(item["dimensions"]), -item["score"], item["page"]))
    required: list[dict] = []
    for dimension in DIMENSION_QUERIES:
        candidates = [item for item in ranked if dimension in item["dimensions"]]
        candidate = min(candidates, key=lambda item: item["page"]) if dimension == "objective" and candidates else (candidates[0] if candidates else None)
        if candidate and candidate not in required:
            required.append(candidate)
    return (required + [item for item in ranked if item not in required])[:14]

def _evidence(paper_ids: list[str]) -> dict[str, list[dict]]:
    if len(set(paper_ids)) != len(paper_ids): raise HTTPException(422, "Select between 2 and 5 different papers.")
    missing = [paper_id for paper_id in paper_ids if not library().paper(paper_id)]
    if missing: raise HTTPException(404, "One or more selected papers were not found.")
    # Bounded separately per paper so one paper cannot dominate the evidence context.
    return {paper_id: _paper_evidence(paper_id) for paper_id in paper_ids}

@router.post("/compare")
def compare(request: ResearchRequest) -> dict:
    evidence = _evidence(request.paper_ids)
    return _safe(lambda: ResearchService(grounded()).compare(request.paper_ids, evidence))

@router.post("/gaps")
def gaps(request: ResearchRequest) -> dict:
    evidence = _evidence(request.paper_ids)
    return _safe(lambda: ResearchService(grounded()).gaps(evidence))
