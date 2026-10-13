from app.api import research


class FakeLibrary:
    def passages_for_paper(self, paper_id): return []
    def search(self, query, top_k, paper_id):
        if "abstract purpose" in query:
            return [{"chunk_id": "abstract", "paper_id": paper_id, "title": "Study", "page": 1, "section": "Abstract", "text": "This study investigated mobile-device use by advanced English learners using semi-structured interviews and documented their learning practices in sufficient detail.", "score": 0.9}]
        if "limitations" in query:
            return [{"chunk_id": "limit", "paper_id": paper_id, "title": "Study", "page": 10, "section": "Limitations", "text": "The semi-structured interview was conducted only once, which limits the study and means that the evidence cannot establish changes in the participants over an extended period of time.", "score": 0.8}]
        if "results findings" in query:
            return [{"chunk_id": "finding", "paper_id": paper_id, "title": "Study", "page": 9, "section": "Results", "text": "The results showed interviewees used mobile devices for vocabulary practice and described several ways that these tools supported their English-language learning practices.", "score": 0.8}]
        return [{"chunk_id": "tiny", "paper_id": paper_id, "title": "Study", "page": 4, "section": "Methods", "text": "of study", "score": 1.0}]

def test_dimension_retrieval_keeps_ej_style_objective_findings_and_limitations(monkeypatch) -> None:
    monkeypatch.setattr(research, "library", lambda: FakeLibrary())
    evidence = research._paper_evidence("ej")
    by_id = {item["chunk_id"]: item for item in evidence}
    assert "abstract" in by_id and "objective" in by_id["abstract"]["dimensions"]
    assert "finding" in by_id and "key_findings" in by_id["finding"]["dimensions"]
    assert "limit" in by_id and "limitations" in by_id["limit"]["dimensions"]
    assert "tiny" not in by_id
