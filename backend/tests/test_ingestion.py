import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.chunking import chunk_pages
from app.services.library import LocalLibrary
from app.services.pdf import PdfValidationError, extract_pdf, validate_pdf


def test_pdf_validation_rejects_wrong_type_and_size() -> None:
    with pytest.raises(PdfValidationError, match=".pdf extension"):
        validate_pdf("notes.txt", "text/plain", b"%PDF-1.7", 100)
    with pytest.raises(PdfValidationError, match="exceeds"):
        validate_pdf("paper.pdf", "application/pdf", b"%PDF-" + b"x" * 100, 10)


def test_pdf_validation_accepts_signature() -> None:
    validate_pdf("paper.pdf", "application/pdf", b"%PDF-1.7", 100)


def test_upload_endpoint_rejects_non_pdf_before_indexing() -> None:
    response = TestClient(app).post(
        "/papers/upload", files={"file": ("notes.txt", b"not a PDF", "text/plain")}
    )
    assert response.status_code == 422
    assert "extension" in response.json()["detail"]


def test_extraction_is_page_aware_with_mocked_pymupdf(monkeypatch: pytest.MonkeyPatch) -> None:
    class Document:
        needs_pass = False
        page_count = 2
        def __init__(self): self.metadata = {"title": "Study", "author": "Ada"}
        def __iter__(self): return iter([SimpleNamespace(get_text=lambda _: "First page"), SimpleNamespace(get_text=lambda _: "Second page")])
        def close(self): pass
    monkeypatch.setitem(sys.modules, "pymupdf", SimpleNamespace(open=lambda **_: Document()))
    extracted = extract_pdf(b"%PDF-1.7", "source.pdf")
    assert extracted.title == "Study"
    assert extracted.page_text == ["First page", "Second page"]


def test_chunking_is_deterministic_and_preserves_page_and_section() -> None:
    pages = ["Introduction\n" + "alpha " * 120, "Methods\n" + "beta " * 100]
    first = chunk_pages("paper-1", pages, chunk_size=120, overlap=20)
    second = chunk_pages("paper-1", pages, chunk_size=120, overlap=20)
    assert first == second
    assert {chunk.page for chunk in first} == {1, 2}
    assert {chunk.section for chunk in first} == {"Introduction", "Methods"}


class FakeCollection:
    def __init__(self): self.items = {}
    def upsert(self, ids, documents, embeddings, metadatas):
        self.items = {item_id: (doc, metadata) for item_id, doc, metadata in zip(ids, documents, metadatas)}
    def query(self, **kwargs):
        values = list(self.items.values())[:kwargs["n_results"]]
        return {"documents": [[item[0] for item in values]], "metadatas": [[item[1] for item in values]], "distances": [[0.2 for _ in values]]}
    def get(self, **kwargs): return {"ids": list(self.items)}
    def delete(self, ids):
        for item_id in ids: self.items.pop(item_id, None)


def test_library_indexes_and_retrieves_with_deterministic_embedding(tmp_path) -> None:
    library = LocalLibrary(str(tmp_path), "test-model")
    fake = FakeCollection()
    library._collection = fake
    library._embed = lambda texts: [[float(len(text))] for text in texts]  # type: ignore[method-assign]
    extracted = SimpleNamespace(title="Local study", author=None, page_text=["Results\nretrieval evidence is useful."])
    record = library.index("study.pdf", b"%PDF-1.7 deterministic", extracted)
    assert library.list_papers()[0]["id"] == record["id"]
    results = library.search("evidence", 3)
    assert results[0]["title"] == "Local study"
    assert results[0]["page"] == 1
    assert results[0]["score"] == 0.8


def test_hybrid_ranking_is_deterministic_and_keeps_vector_candidates(tmp_path) -> None:
    library = LocalLibrary(str(tmp_path), "test-model")
    vector = [
        {"chunk_id": "one", "score": 0.8, "page": 1, "section": "Introduction", "text": "general context", "paper_id": "p", "title": "Study"},
        {"chunk_id": "two", "score": 0.7, "page": 2, "section": "Methods", "text": "participants and procedure", "paper_id": "p", "title": "Study"},
    ]
    passages = vector + [
        {"chunk_id": "three", "score": 1.0, "page": 3, "section": "Results", "text": "The results report a participant outcome.", "paper_id": "p", "title": "Study"}
    ]
    library.search = lambda *_args, **_kwargs: [dict(item) for item in vector]  # type: ignore[method-assign]
    library.passages_for_paper = lambda _paper_id: [dict(item) for item in passages]  # type: ignore[method-assign]
    first = library.search_hybrid("participant results", 3, "p")
    second = library.search_hybrid("participant results", 3, "p")
    assert first == second
    assert {item["chunk_id"] for item in first} == {"one", "two", "three"}
    assert first == sorted(first, key=lambda item: (-item["score"], item["page"], item["chunk_id"]))
