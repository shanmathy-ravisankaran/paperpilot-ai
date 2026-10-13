from app.services.evaluation import load_dataset, retrieval_metrics


def test_dataset_is_versioned_and_has_curated_prompt_count() -> None:
    dataset = load_dataset()
    assert dataset["version"] == "1.0.0"
    assert 30 <= len(dataset["examples"]) <= 50
    assert all(item["manual_verification"] for item in dataset["examples"])

def test_retrieval_metrics_calculate_hits_and_mrr() -> None:
    rows = [{"answerable": True, "expected_pages": [2], "retrieved": [{"page": 2}]}, {"answerable": True, "expected_pages": [4], "retrieved": [{"page": 1}, {"page": 4}]}, {"answerable": False, "expected_pages": [], "retrieved": []}]
    metrics = retrieval_metrics(rows)
    assert metrics["hit_at_1"] == 0.5 and metrics["hit_at_3"] == 1.0 and metrics["mrr"] == 0.75

def test_unanswerable_rows_are_excluded_only_from_rank_metrics() -> None:
    rows = [{"answerable": False, "expected_pages": [], "retrieved": [{"page": 1}]}, {"answerable": True, "expected_pages": [2], "retrieved": [{"page": 2}]}]
    assert retrieval_metrics(rows)["hit_at_1"] == 1.0
