import json

import pytest

from app.services.grounding import INSUFFICIENT, GroundedService, GroundingError
from app.services.llm import LlmError


class FakeClient:
    def __init__(self, reply): self.reply = reply
    def complete(self, prompt, json_schema=None):
        if isinstance(self.reply, Exception): raise self.reply
        return json.dumps(self.reply)

class SequenceClient:
    def __init__(self, replies): self.replies = iter(replies); self.calls = 0
    def complete(self, prompt, json_schema=None): self.calls += 1; return next(self.replies)

PASSAGES = [{"chunk_id": "chunk-a", "paper_id": "paper-a", "title": "Study", "page": 2, "section": "Results", "text": "The intervention improved outcomes.", "score": 0.9}]

def test_answer_maps_valid_stable_citation_to_retrieved_chunk() -> None:
    result = GroundedService(FakeClient({"answer": "It improved outcomes.", "citations": ["C1"], "insufficient_evidence": False})).answer("What happened?", PASSAGES)
    assert result["sources"][0]["citation_id"] == "C1" and result["sources"][0]["chunk_id"] == "chunk-a"

def test_answer_rejects_fabricated_citation() -> None:
    with pytest.raises(GroundingError, match="not in the retrieved"):
        GroundedService(FakeClient({"answer": "Unsupported.", "citations": ["C99"], "insufficient_evidence": False})).answer("Question", PASSAGES)

def test_answer_returns_explicit_insufficiency_without_citations() -> None:
    result = GroundedService(FakeClient({"answer": "Maybe.", "citations": [], "insufficient_evidence": True})).answer("Question", PASSAGES)
    assert result["answer"] == INSUFFICIENT

def test_model_error_is_propagated_safely() -> None:
    with pytest.raises(LlmError):
        GroundedService(FakeClient(LlmError("model unavailable"))).answer("Question", PASSAGES)

def test_summary_generation_validates_supported_and_not_stated_sections() -> None:
    supported = {"text": "The intervention improved outcomes.", "citations": ["C1"], "not_stated": False}
    missing = {"text": "anything", "citations": [], "not_stated": True}
    result = GroundedService(FakeClient({"sections": {"objective": supported, "methodology": missing, "findings": supported, "limitations": missing, "contributions": supported}})).summary(PASSAGES)
    assert result["sections"]["methodology"]["text"] == "Not stated in the paper."
    assert result["sources"][0]["citation_id"] == "C1"

def test_malformed_json_retries_then_returns_actionable_error() -> None:
    client = SequenceClient(["not json", "still not json"])
    with pytest.raises(GroundingError, match="after retrying"):
        GroundedService(client).summary(PASSAGES)
    assert client.calls == 2

def test_missing_summary_sections_retries_then_rejects_schema() -> None:
    client = SequenceClient([json.dumps({"sections": {}}), json.dumps({"sections": {}})])
    with pytest.raises(GroundingError, match="after retrying"):
        GroundedService(client).summary(PASSAGES)

def test_summary_rejects_invalid_citation_after_schema_validation() -> None:
    section = {"text": "Claim", "citations": ["C99"], "not_stated": False}
    reply = {"sections": {name: section for name in ("objective", "methodology", "findings", "limitations", "contributions")}}
    with pytest.raises(GroundingError, match="not in the retrieved"):
        GroundedService(FakeClient(reply)).summary(PASSAGES)
