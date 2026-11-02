import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.grounding import GroundedService, GroundingError
from app.services.research import GapsPayload, PaperFields, ResearchService


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

def test_comparison_retries_cross_paper_profile_leakage_at_its_own_stage() -> None:
    reply = [profile(["P2C1"]), profile(["P1C1"]), profile(["P2C1"]), {"relationships": []}]
    result = ResearchService(GroundedService(FakeClient(reply))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["papers"][0]["objective"]["citations"] == ["P1C1"]

def test_relationship_requires_two_papers() -> None:
    invalid = {"relationships": [{"classification": "agreement", "explanation": "Same", "citations": ["P1C1"], "limitation": "Limited"}]}
    reply = [profile(["P1C1"]), profile(["P2C1"]), invalid, invalid]
    with pytest.raises(GroundingError, match="relationships stage after retrying"):
        ResearchService(GroundedService(FakeClient(reply))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})

def test_gap_requires_valid_citation() -> None:
    invalid = {"gaps": [{"title": "Gap", "category": "methodological", "explanation": "x", "citations": ["P99"], "why_it_might_matter": "x", "follow_up_question": "x", "author_stated": False}], "limitation": "Limited evidence."}
    valid = {"gaps": [{"title": "Gap", "category": "methodological", "explanation": "x", "citations": ["P1C1"], "why_it_might_matter": "x", "follow_up_question": "x", "author_stated": False}], "limitation": "Limited evidence."}
    result = ResearchService(GroundedService(FakeClient([invalid, valid]))).gaps({"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["gaps"][0]["citations"] == ["P1C1"]


def test_retry_exhaustion_keeps_invalid_citations_rejected() -> None:
    invalid = {"gaps": [{"title": "Gap", "category": "methodological", "explanation": "x", "citations": ["C1"], "why_it_might_matter": "x", "follow_up_question": "x", "author_stated": False}], "limitation": "Limited evidence."}
    with pytest.raises(GroundingError, match="gaps stage after retrying"):
        ResearchService(GroundedService(FakeClient([invalid, invalid]))).gaps({"a": passages("a", "A"), "b": passages("b", "B")})


def test_relationship_stage_retries_invalid_single_paper_citations() -> None:
    invalid_relationship = {"relationships": [{"classification": "agreement", "explanation": "Same", "citations": ["P1C1"], "limitation": "Limited"}]}
    valid_relationship = {"relationships": [{"classification": "agreement", "explanation": "Same", "citations": ["P1C1", "P2C1"], "limitation": "Limited"}]}
    replies = [profile(["P1C1"]), profile(["P2C1"]), invalid_relationship, valid_relationship]
    result = ResearchService(GroundedService(FakeClient(replies))).compare(["a", "b"], {"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["relationships"][0]["citations"] == ["P1C1", "P2C1"]


def test_stage_schema_constrains_each_citation_array_to_its_allowed_ids() -> None:
    schema = ResearchService._citation_schema(GapsPayload, ["P1C1", "P2C4"])
    assert schema["$defs"]["Gap"]["properties"]["citations"]["items"]["enum"] == ["P1C1", "P2C4"]
    profile_schema = ResearchService._citation_schema(PaperFields, ["P1C2"])
    assert profile_schema["$defs"]["Cell"]["properties"]["citations"]["items"]["enum"] == ["P1C2"]

def test_gaps_accepts_no_well_supported_outcome() -> None:
    reply = {"gaps": [], "limitation": "No well-supported gaps identified."}
    result = ResearchService(GroundedService(FakeClient(reply))).gaps({"a": passages("a", "A"), "b": passages("b", "B")})
    assert result["gaps"] == []

def test_research_endpoint_validates_selection_and_missing_papers() -> None:
    client = TestClient(app)
    assert client.post("/research/compare", json={"paper_ids": ["one"]}).status_code == 422
    assert client.post("/research/gaps", json={"paper_ids": ["missing-a", "missing-b"]}).status_code == 404
