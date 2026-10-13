from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings

from .library import LocalLibrary

DATASET = Path(__file__).parents[2] / "evaluation" / "dataset.v1.json"

def load_dataset() -> dict[str, Any]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    if not data.get("version") or not 30 <= len(data.get("examples", [])) <= 50: raise ValueError("Evaluation dataset is invalid.")
    for item in data["examples"]:
        if not {"id", "question", "pages", "answerable", "reference", "manual_verification"} <= item.keys(): raise ValueError("Evaluation example is incomplete.")
    return data

def retrieval_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    answerable = [row for row in rows if row["answerable"]]
    if not answerable: return {"hit_at_1": 0, "hit_at_3": 0, "hit_at_5": 0, "mrr": 0}
    def hit(k): return sum(any(p["page"] in row["expected_pages"] for p in row["retrieved"][:k]) for row in answerable) / len(answerable)
    reciprocal = []
    for row in answerable:
        rank = next((i + 1 for i, p in enumerate(row["retrieved"]) if p["page"] in row["expected_pages"]), 0)
        reciprocal.append(1 / rank if rank else 0)
    return {"hit_at_1": round(hit(1), 4), "hit_at_3": round(hit(3), 4), "hit_at_5": round(hit(5), 4), "mrr": round(sum(reciprocal) / len(reciprocal), 4)}

def _rows(library: LocalLibrary, examples: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    rows=[]
    for example in examples:
        if example["paper_id"] is None: continue
        start=time.perf_counter(); retrieved = library.search_hybrid(example["question"], 5, example["paper_id"]) if mode == "hybrid_section" else library.search(example["question"], 5, example["paper_id"]); elapsed=(time.perf_counter()-start)*1000
        rows.append({"id":example["id"],"question":example["question"],"answerable":example["answerable"],"expected_pages":example["pages"],"manual_verification":example["manual_verification"],"retrieved":[{"chunk_id":p["chunk_id"],"page":p["page"],"score":p["score"]} for p in retrieved],"retrieval_latency_ms":round(elapsed,2)})
    return rows

def run_retrieval(settings: Settings, library: LocalLibrary) -> dict[str, Any]:
    dataset = load_dataset(); rows = []
    rows = _rows(library, dataset["examples"], "vector")
    candidate = _rows(library, dataset["examples"], "hybrid_section")
    metrics = retrieval_metrics(rows)
    metrics["mean_retrieval_latency_ms"] = round(sum(row["retrieval_latency_ms"] for row in rows) / len(rows), 2) if rows else 0
    candidate_metrics=retrieval_metrics(candidate); candidate_metrics["mean_retrieval_latency_ms"]=round(sum(x["retrieval_latency_ms"] for x in candidate)/len(candidate),2)
    return {"run_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"), "timestamp": datetime.now(UTC).isoformat(), "dataset_version": dataset["version"], "dataset_size": len(dataset["examples"]), "evaluated_retrieval_examples": len(rows), "answerable_denominator": len([x for x in rows if x["answerable"]]), "unanswerable_excluded_from_hit_metrics": len([x for x in rows if not x["answerable"]]), "cross_paper_skipped": len([x for x in dataset["examples"] if x["paper_id"] is None]), "embedding_model": settings.embedding_model, "llm_model": settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model, "retrieval_config": {"top_k": 5, "scope": "single-paper", "baseline":"vector", "candidate":"hybrid_section", "tuning":"no learned tuning; deterministic heuristic evaluated on same small set"}, "metrics": metrics, "candidate_metrics":candidate_metrics, "results": rows, "candidate_results":candidate, "limitations": ["Page-level relevance is a proxy for chunk relevance.", "Cross-paper and semantic faithfulness checks require manual review.", "Citation validity measures source linkage, not factual correctness."]}

def save_run(settings: Settings, result: dict[str, Any]) -> Path:
    directory = Path(settings.data_dir) / "evaluations"; directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{result['run_id']}.json"; target.write_text(json.dumps(result, indent=2), encoding="utf-8"); return target

def list_runs(settings: Settings) -> list[dict[str, Any]]:
    directory = Path(settings.data_dir) / "evaluations"
    if not directory.exists(): return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"), reverse=True)]
