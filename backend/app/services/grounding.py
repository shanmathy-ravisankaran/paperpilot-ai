from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from .llm import LlmClient

INSUFFICIENT = "The uploaded papers do not provide enough information to answer this question."
logger = logging.getLogger(__name__)

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class _AnswerPayload(_Strict):
    answer: str
    citations: list[str]
    insufficient_evidence: bool

class _SummaryItem(_Strict):
    text: str
    citations: list[str]
    not_stated: bool

class _SummarySections(_Strict):
    objective: _SummaryItem
    methodology: _SummaryItem
    findings: _SummaryItem
    limitations: _SummaryItem
    contributions: _SummaryItem

class _SummaryPayload(_Strict):
    sections: _SummarySections

class GroundingError(ValueError): pass

@dataclass(frozen=True)
class GroundedService:
    client: LlmClient

    def _evidence(self, passages: list[dict[str, Any]]) -> tuple[str, dict[str, dict[str, Any]]]:
        mapped = {f"C{i + 1}": passage for i, passage in enumerate(passages)}
        text = "\n\n".join(f"[{key}] {item['title']} | page {item['page']} | {item['section']}\n{item['text']}" for key, item in mapped.items())
        return text, mapped

    @staticmethod
    def _json(text: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GroundingError("The model did not return the required structured response.") from exc
        if not isinstance(value, dict): raise GroundingError("The model response must be a JSON object.")
        return value

    def _structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        """Ask twice at most; logs only format metadata, never evidence or model text."""
        for attempt in range(2):
            try:
                raw = self.client.complete(prompt, schema.model_json_schema())
                return schema.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError, GroundingError) as exc:
                logger.warning("LLM structured output rejected: schema=%s attempt=%d error=%s", schema.__name__, attempt + 1, type(exc).__name__)
                if attempt == 1:
                    raise GroundingError("The local model returned an invalid structured response after retrying. Try again or use a smaller paper scope.") from exc
                prompt += "\nYour prior response did not match the required JSON schema. Return only a complete JSON object matching it exactly."
        raise AssertionError("unreachable")

    @staticmethod
    def _citations(value: Any, evidence: dict[str, dict[str, Any]]) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise GroundingError("The model response has invalid citations.")
        if any(item not in evidence for item in value):
            raise GroundingError("The model returned a citation that is not in the retrieved evidence.")
        return value

    def answer(self, question: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
        if not passages: return {"answer": INSUFFICIENT, "citations": [], "sources": []}
        evidence_text, evidence = self._evidence(passages)
        prompt = f"""Answer the research question using ONLY the evidence below. Do not use outside knowledge. If the evidence does not answer it, set insufficient_evidence true and use exactly this answer: {INSUFFICIENT!r}. Return JSON only: {{\"answer\": string, \"citations\": [\"C1\"], \"insufficient_evidence\": boolean}}. Every factual answer needs at least one citation; citation IDs must be from the evidence.
Question: {question}\nEvidence:\n{evidence_text}"""
        result = self._structured(prompt, _AnswerPayload)
        citations = self._citations(result.citations, evidence)
        if result.insufficient_evidence is True or not citations:
            return {"answer": INSUFFICIENT, "citations": [], "sources": []}
        if not result.answer.strip(): raise GroundingError("The model returned an invalid answer.")
        return {"answer": result.answer.strip(), "citations": citations, "sources": [{"citation_id": key, **evidence[key]} for key in citations]}

    def summary(self, passages: list[dict[str, Any]]) -> dict[str, Any]:
        if not passages: return {"sections": self._empty_summary(), "sources": []}
        evidence_text, evidence = self._evidence(passages)
        prompt = f"""Summarize this paper using ONLY supplied evidence. Return JSON only with a sections object containing objective, methodology, findings, limitations, contributions. Each section is {{\"text\": string, \"citations\": [\"C1\"], \"not_stated\": boolean}}. If a section is unsupported, set text to 'Not stated in the paper.', citations to [], and not_stated true. Never infer missing information.\nEvidence:\n{evidence_text}"""
        result = self._structured(prompt, _SummaryPayload)
        raw = result.sections.model_dump()
        sections: dict[str, dict[str, Any]] = {}
        used: list[str] = []
        for name in self._empty_summary():
            item = raw.get(name)
            if not isinstance(item, dict): raise GroundingError(f"The {name} summary section is missing.")
            if item.get("not_stated") is True:
                sections[name] = {"text": "Not stated in the paper.", "citations": [], "not_stated": True}; continue
            text, citations = item.get("text"), self._citations(item.get("citations"), evidence)
            if not isinstance(text, str) or not text.strip() or not citations: raise GroundingError(f"The {name} section is unsupported.")
            sections[name] = {"text": text.strip(), "citations": citations, "not_stated": False}; used.extend(citations)
        unique = list(dict.fromkeys(used))
        return {"sections": sections, "sources": [{"citation_id": key, **evidence[key]} for key in unique]}

    @staticmethod
    def _empty_summary() -> dict[str, dict[str, Any]]:
        return {name: {"text": "Not stated in the paper.", "citations": [], "not_stated": True} for name in ("objective", "methodology", "findings", "limitations", "contributions")}
