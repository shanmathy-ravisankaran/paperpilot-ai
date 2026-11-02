from __future__ import annotations

import logging
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .grounding import GroundedService, GroundingError

NOT_STATED = "Not stated in retrieved evidence."
logger = logging.getLogger(__name__)

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Cell(_Strict):
    text: str
    citations: list[str]
    not_stated: bool

class PaperMatrix(_Strict):
    paper_id: str
    objective: Cell
    research_questions: Cell
    methodology: Cell
    sample_population: Cell
    data_collection: Cell
    analysis_approach: Cell
    key_findings: Cell
    limitations: Cell
    contributions: Cell

class PaperFields(_Strict):
    objective: Cell
    research_questions: Cell
    methodology: Cell
    sample_population: Cell
    data_collection: Cell
    analysis_approach: Cell
    key_findings: Cell
    limitations: Cell
    contributions: Cell

class Relationship(_Strict):
    classification: Literal["agreement", "potential_contradiction", "different_context_or_methodology", "insufficient_evidence"]
    explanation: str
    citations: list[str]
    limitation: str

class ComparePayload(_Strict):
    papers: list[PaperMatrix]
    relationships: list[Relationship]

class RelationshipsPayload(_Strict):
    relationships: list[Relationship]

class Gap(_Strict):
    title: str
    category: Literal["population_or_sample", "methodological", "setting_or_context", "unresolved_findings", "author_suggested_future_work"]
    explanation: str
    citations: list[str]
    why_it_might_matter: str
    follow_up_question: str
    author_stated: bool

class GapsPayload(_Strict):
    gaps: list[Gap]
    limitation: str

FIELDS = ("objective", "research_questions", "methodology", "sample_population", "data_collection", "analysis_approach", "key_findings", "limitations", "contributions")

class ResearchService:
    def __init__(self, grounding: GroundedService, timeout_seconds: int = 300):
        self.grounding = grounding
        self.timeout_seconds = timeout_seconds
        self._deadline: float | None = None

    def _start_request(self) -> None:
        self._deadline = time.monotonic() + self.timeout_seconds

    def _remaining_seconds(self) -> float:
        return float(self.timeout_seconds) if self._deadline is None else self._deadline - time.monotonic()

    @staticmethod
    def _citation_schema(schema: type[BaseModel], allowed: list[str]) -> dict[str, Any]:
        """Constrain every citations array in the provider schema to this stage's IDs."""
        result = schema.model_json_schema()
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict) and isinstance(properties.get("citations"), dict):
                    items = properties["citations"].setdefault("items", {})
                    if isinstance(items, dict):
                        items["enum"] = allowed
                for nested in value.values(): visit(nested)
            elif isinstance(value, list):
                for nested in value: visit(nested)
        visit(result)
        return result

    @staticmethod
    def _returned_citation_ids(result: BaseModel) -> list[str]:
        found: list[str] = []
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key == "citations" and isinstance(nested, list):
                        found.extend(item for item in nested if isinstance(item, str))
                    else: visit(nested)
            elif isinstance(value, list):
                for nested in value: visit(nested)
        visit(result.model_dump())
        return list(dict.fromkeys(found))

    def _evidence(self, per_paper: dict[str, list[dict[str, Any]]]) -> tuple[str, dict[str, dict[str, Any]]]:
        mapped: dict[str, dict[str, Any]] = {}
        lines: list[str] = []
        for paper_number, (paper_id, passages) in enumerate(per_paper.items(), 1):
            for chunk_number, passage in enumerate(passages, 1):
                citation_id = f"P{paper_number}C{chunk_number}"
                mapped[citation_id] = passage
                dimensions = ", ".join(passage.get("dimensions", [])) or "general"
                lines.append(f"[{citation_id}] paper_id={paper_id}; relevant dimensions={dimensions}; {passage['title']}; page {passage['page']}; {passage['section']}\n{passage['text']}")
        return "\n\n".join(lines), mapped

    def _sources(self, citation_ids: list[str], evidence: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"citation_id": key, **evidence[key]} for key in dict.fromkeys(citation_ids)]

    def _cell(self, item: Cell, evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
        citations = self.grounding._citations(item.citations, evidence)
        if item.not_stated or not citations:
            return {"text": NOT_STATED, "citations": [], "not_stated": True}
        if not item.text.strip(): raise GroundingError("A comparison cell is empty despite citations.")
        return {"text": item.text.strip(), "citations": citations, "not_stated": False}

    def _stage(self, stage: str, prompt: str, schema: type[BaseModel], evidence: dict[str, dict[str, Any]], validate: Any) -> BaseModel:
        """Validate citations at the same scope as generation and retry that stage once."""
        allowed = list(evidence)
        citation_schema = self._citation_schema(schema, allowed)
        for attempt in range(2):
            if self._remaining_seconds() <= 0:
                raise GroundingError("The research request exceeded its bounded local inference time. Try fewer papers or retry when Ollama is idle.")
            started = time.perf_counter()
            result: BaseModel | None = None
            try:
                result = self.grounding._structured(prompt, schema, citation_schema)
                validate(result, evidence)
                logger.info("Research stage completed: stage=%s attempt=%d elapsed_ms=%d allowed_ids=%s returned_ids=%s citation_validation=passed", stage, attempt + 1, round((time.perf_counter() - started) * 1000), ",".join(allowed), ",".join(self._returned_citation_ids(result)))
                return result
            except GroundingError as exc:
                returned = self._returned_citation_ids(result) if result is not None else []
                invalid = [citation for citation in returned if citation not in evidence]
                logger.warning(
                    "Research stage rejected: stage=%s attempt=%d elapsed_ms=%d allowed_ids=%s returned_ids=%s invalid_ids=%s error=%s",
                    stage, attempt + 1, round((time.perf_counter() - started) * 1000), ",".join(allowed), ",".join(returned), ",".join(invalid), str(exc),
                )
                if attempt == 1:
                    raise GroundingError(f"The local model returned invalid citations for the {stage} stage after retrying.") from exc
                prompt += f"\nYour prior response used citations outside this stage's retrieved evidence. Retry ONLY with these exact case-sensitive IDs: {', '.join(allowed)}. Do not use any other citation ID."
        raise AssertionError("unreachable")

    def _profile(self, paper_id: str, prompt: str, evidence: dict[str, dict[str, Any]]) -> PaperFields:
        def validate(result: PaperFields, scoped: dict[str, dict[str, Any]]) -> None:
            for field in FIELDS:
                item = getattr(result, field)
                self.grounding._citations(item.citations, scoped)
                if any(scoped[citation]["paper_id"] != paper_id for citation in item.citations):
                    raise GroundingError("A paper profile cited evidence from a different paper.")
        return self._stage(f"profile:{paper_id}", prompt, PaperFields, evidence, validate)  # type: ignore[return-value]

    def compare(self, paper_ids: list[str], per_paper: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        self._start_request()
        evidence_text, evidence = self._evidence(per_paper)
        allowed_ids = ", ".join(evidence)
        matrices: list[dict[str, Any]] = []
        used: list[str] = []
        # Stage one compact schema-constrained generation per paper. This keeps qwen2.5:3b
        # from having to emit a large nested multi-paper object in a single request.
        for paper_id in paper_ids:
            own_ids = [key for key, value in evidence.items() if value["paper_id"] == paper_id]
            own_evidence = "\n\n".join(f"[{key}] relevant dimensions={', '.join(evidence[key].get('dimensions', [])) or 'general'}; {evidence[key]['title']}; page {evidence[key]['page']}; {evidence[key]['section']}\n{evidence[key]['text']}" for key in own_ids)
            own_allowed = ", ".join(own_ids)
            prompt = f"""Create a factual structured profile for paper_id={paper_id} using ONLY this paper's evidence. Use passages labeled relevant to each field. The objective must come from abstract/explicit purpose/investigation evidence, never discussion recommendations. Populate research_questions only when the passage explicitly states a research question or hypothesis; an aim or purpose is not a research question. Key_findings must be substantive study outcomes, never demographic/descriptive sample statistics or a chapter introduction. Limitations require an explicit limitation passage. Contributions require a substantive evidence-backed contribution, never a heading, table of contents, section outline, or future-discussion statement. Citation IDs are case-sensitive and MUST be chosen verbatim only from this list: {own_allowed}. Never use C1, page numbers, brackets, or invented IDs. If the field is not supported by retrieved evidence, use text 'Not stated in retrieved evidence.', empty citations, and not_stated true. This does NOT mean it is absent from the full paper. Do not infer missing information.\nEvidence:\n{own_evidence}"""
            own_evidence = {key: evidence[key] for key in own_ids}
            paper = self._profile(paper_id, prompt, own_evidence)
            row = {"paper_id": paper_id}
            for field in FIELDS:
                cell = self._cell(getattr(paper, field), evidence)
                for citation in cell["citations"]:
                    if evidence[citation]["paper_id"] != paper_id:
                        raise GroundingError("A paper comparison cell cited evidence from a different paper.")
                row[field] = cell; used.extend(cell["citations"])
            matrices.append(row)
        prompt = f"""Compare ONLY the selected-paper evidence below. Return JSON matching the schema. Citation IDs are case-sensitive and MUST be chosen verbatim only from this list: {allowed_ids}. Never use C1, page numbers, brackets, or invented IDs. Relationships are AI-assisted interpretations, not scientific conclusions. A relationship classified agreement, potential_contradiction, or different_context_or_methodology requires at least two citations from two different paper_ids. Do not call wording differences a contradiction; use different_context_or_methodology or insufficient_evidence. Return an empty list when weak.\nEvidence:\n{evidence_text}"""
        def validate_relationships(payload: RelationshipsPayload, scoped: dict[str, dict[str, Any]]) -> None:
            for item in payload.relationships:
                citations = self.grounding._citations(item.citations, scoped)
                source_papers = {scoped[citation]["paper_id"] for citation in citations}
                if item.classification != "insufficient_evidence" and (len(citations) < 2 or len(source_papers) < 2):
                    raise GroundingError("A cross-paper relationship needs evidence from at least two selected papers.")
        payload = self._stage("relationships", prompt, RelationshipsPayload, evidence, validate_relationships)
        relationships: list[dict[str, Any]] = []
        for item in payload.relationships:
            citations = self.grounding._citations(item.citations, evidence)
            source_papers = {evidence[citation]["paper_id"] for citation in citations}
            if item.classification != "insufficient_evidence" and (len(citations) < 2 or len(source_papers) < 2):
                raise GroundingError("A cross-paper relationship needs evidence from at least two selected papers.")
            relationships.append({**item.model_dump(), "citations": citations}); used.extend(citations)
        return {"papers": matrices, "relationships": relationships, "sources": self._sources(used, evidence)}

    def gaps(self, per_paper: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        self._start_request()
        evidence_text, evidence = self._evidence(per_paper)
        allowed_ids = ", ".join(evidence)
        prompt = f"""Identify only well-supported potential research-gap hypotheses from the selected-paper evidence. Return JSON matching the schema. Citation IDs are case-sensitive and MUST be chosen verbatim only from this list: {allowed_ids}. Never use C1, page numbers, brackets, or invented IDs. A gap is an AI-generated hypothesis—not proof of novelty in wider literature. Cite every claim. Prefer author-stated limitations/future work; mark author_stated true only when explicit. If no item is supported, return gaps [] and an explicit limitation saying no well-supported gaps were identified. Never invent novelty, impact, confidence, statistics, or uncited findings.\nEvidence:\n{evidence_text}"""
        def validate_gaps(payload: GapsPayload, scoped: dict[str, dict[str, Any]]) -> None:
            for item in payload.gaps:
                citations = self.grounding._citations(item.citations, scoped)
                if not citations:
                    raise GroundingError("A gap hypothesis requires supporting evidence.")
        payload = self._stage("gaps", prompt, GapsPayload, evidence, validate_gaps)
        gaps: list[dict[str, Any]] = []; used: list[str] = []
        for item in payload.gaps:
            citations = self.grounding._citations(item.citations, evidence)
            if not citations: raise GroundingError("A gap hypothesis requires supporting evidence.")
            gaps.append({**item.model_dump(), "citations": citations, "label": "AI-generated hypothesis — not proof of novelty"}); used.extend(citations)
        return {"gaps": gaps, "limitation": payload.limitation.strip(), "sources": self._sources(used, evidence)}
