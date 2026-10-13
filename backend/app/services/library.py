from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .chunking import chunk_pages
from .pdf import ExtractedPaper


class LocalLibrary:
    def __init__(self, data_dir: str, model_name: str):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.root / "papers.json"
        self.model_name = model_name
        self._model: Any = None
        self._collection: Any = None

    def _catalog(self) -> dict[str, dict[str, Any]]:
        if not self.catalog_path.exists():
            return {}
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def _save_catalog(self, catalog: dict[str, dict[str, Any]]) -> None:
        self.catalog_path.write_text(json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # Retrieval stays local after setup; do not make network checks per request.
            self._model = SentenceTransformer(self.model_name, device="cpu", local_files_only=True)
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

    def _store(self) -> Any:
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.root / "chroma"))
            self._collection = client.get_or_create_collection("paper_chunks", metadata={"hnsw:space": "cosine"})
        return self._collection

    def index(self, source_name: str, raw_data: bytes, extracted: ExtractedPaper) -> dict[str, Any]:
        paper_id = hashlib.sha256(raw_data).hexdigest()[:24]
        chunks = chunk_pages(paper_id, extracted.page_text)
        if not chunks:
            raise ValueError("No indexable text was found in this PDF.")
        record = {"id": paper_id, "title": extracted.title, "author": extracted.author,
                  "filename": source_name, "page_count": len(extracted.page_text), "chunk_count": len(chunks),
                  "indexed_at": datetime.now(UTC).isoformat()}
        collection = self._store()
        # Preserve prior vectors until replacement vectors are successfully written.
        existing = collection.get(where={"paper_id": paper_id}, include=[])
        collection.upsert(ids=[chunk.id for chunk in chunks], documents=[chunk.text for chunk in chunks],
            embeddings=self._embed([chunk.text for chunk in chunks]),
            metadatas=[{"paper_id": paper_id, "title": extracted.title, "page": chunk.page,
                        "section": chunk.section, "chunk_id": chunk.id} for chunk in chunks])
        stale_ids = set(existing.get("ids", [])) - {chunk.id for chunk in chunks}
        if stale_ids:
            collection.delete(ids=list(stale_ids))
        catalog = self._catalog()
        catalog[paper_id] = record
        self._save_catalog(catalog)
        return record

    def list_papers(self) -> list[dict[str, Any]]:
        return sorted(self._catalog().values(), key=lambda item: item["indexed_at"], reverse=True)

    def paper(self, paper_id: str) -> dict[str, Any] | None:
        return self._catalog().get(paper_id)

    def passages_for_paper(self, paper_id: str) -> list[dict[str, Any]]:
        """Read locally indexed passages without embedding a query."""
        result = self._store().get(where={"paper_id": paper_id}, include=["documents", "metadatas"])
        return [{"text": text, "score": 1.0, "paper_id": meta["paper_id"], "title": meta["title"],
                 "page": meta["page"], "section": meta["section"], "chunk_id": meta["chunk_id"]}
                for text, meta in zip(result.get("documents", []), result.get("metadatas", []))]

    def search(self, query: str, top_k: int, paper_id: str | None = None) -> list[dict[str, Any]]:
        query_args: dict[str, Any] = {"query_embeddings": self._embed([query]), "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]}
        if paper_id:
            query_args["where"] = {"paper_id": paper_id}
        result = self._store().query(**query_args)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [{"text": text, "score": round(1 - float(distance), 4), "paper_id": meta["paper_id"],
                 "title": meta["title"], "page": meta["page"], "section": meta["section"], "chunk_id": meta["chunk_id"]}
                for text, meta, distance in zip(documents, metadatas, distances)]

    def search_hybrid(self, query: str, top_k: int, paper_id: str) -> list[dict[str, Any]]:
        """Deterministic lexical/section rerank for evaluation; no extra model or training."""
        vector = {item["chunk_id"]: item for item in self.search(query, 20, paper_id)}
        terms = {term for term in query.lower().replace("?", "").split() if len(term) > 2}
        for item in self.passages_for_paper(paper_id):
            text = (item["section"] + " " + item["text"]).lower()
            overlap = sum(term in text for term in terms) / max(len(terms), 1)
            if overlap:
                item["score"] = round(0.65 * vector.get(item["chunk_id"], {"score": 0})["score"] + 0.35 * overlap + (0.05 if any(term in item["section"].lower() for term in terms) else 0), 4)
                vector[item["chunk_id"]] = item
        return sorted(vector.values(), key=lambda item: (-item["score"], item["page"], item["chunk_id"]))[:top_k]
