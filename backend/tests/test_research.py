import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.grounding import GroundedService, GroundingError
from app.services.research import ResearchService


class FakeClient:
    def __init__(self, reply): self.reply = iter(reply if isinstance(reply, list) else [reply])
    def complete(self, prompt, json_schema=None): return json.dumps(next(self.reply))

def passages(paper_id: str, title: str):
    return [{"chunk_id": f"{paper_id}-chunk", "paper_id": paper_id, "title": title, "page": 1, "section": "Results", "text": "Evidence from this paper.", "score": 0.9}]

def cell(citations): return {"text": "Supported statement.", "citations": citations, "not_stated": False}
def row(paper_id, citations): return {"paper_id": paper_id, **{name: cell(citations) for name in ("objective", "research_questions", "methodology", "sample_population", "data_collection", "analysis_approach", "key_findings", "limitations", "contributions")}}
def profile(citations): return {name: cell(citations) for name in ("objective", "research_questions", "methodology", "sample_population", "data_collection", "analysis_approach", "key_findings", "limitations", "contributions")}

def test_comparison_keeps_citations_with_their_own_paper() -> None:
    reply = [profile(["P1C1"]), profile(["P2C1"]), {"relationships": []}]
    result = ResearchService(GroundedService(FakeClient(reply))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["papers"][0]["objective"]["citations"] == ["P1C1"]

def test_comparison_rejects_cross_paper_source_mixing() -> None:
    reply = [profile(["P2C1"]), profile(["P2C1"]), {"relationships": []}]
    with pytest.raises(GroundingError, match="different paper"):
        ResearchService(GroundedService(FakeClient(reply))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})

def test_relationship_requires_two_papers() -> None:
    reply = [profile(["P1C1"]), profile(["P2C1"]), {"relationships": [{"classification": "agreement", "explanation": "Same", "citations": ["P1C1"], "limitation": "Limited"}]}]
    with pytest.raises(GroundingError, match="at least two"):
        ResearchService(GroundedService(FakeClient(reply))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})

def test_gap_requires_valid_citation() -> None:
    reply = {"gaps": [{"title": "Gap", "category": "methodological", "explanation": "x", "citations": ["P99"], "why_it_might_matter": "x", "follow_up_question": "x", "author_stated": False}], "limitation": "Limited evidence."}
    with pytest.raises(GroundingError, match="not in the retrieved"):
        ResearchService(GroundedService(FakeClient(reply))).gaps({"a": passages("a", "A"), "b": passages("b", "B")})

def test_gaps_accepts_no_well_supported_outcome() -> None:
    reply = {"gaps": [], "limitation": "No well-supported gaps identified."}
    result = ResearchService(GroundedService(FakeClient(reply))).gaps({"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["gaps"] == []

def test_research_endpoint_validates_selection_and_missing_papers() -> None:
    client = TestClient(app)
    assert client.post("/research/compare", json={"paper_ids": ["one"]}).status_code == 422
    assert client.post("/research/gaps", json={"paper_ids": ["missing-a", "missing-b"]}).status_code == 404
