from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.A_memorix.core.utils import retrieval_tuning_manager as tuning_module
from src.A_memorix.core.utils.retrieval_tuning_manager import (
    RetrievalQueryCase,
    RetrievalTuningManager,
    RetrievalTuningTaskRecord,
)


class _FakePlugin:
    def __init__(self) -> None:
        self.config = {
            "retrieval": {
                "top_k_paragraphs": 20,
                "top_k_relations": 10,
                "top_k_final": 10,
                "alpha": 0.5,
                "enable_ppr": True,
                "ppr_alpha": 0.85,
                "ppr_timeout_seconds": 1.5,
                "vector_pools": {"mode": "single"},
            },
            "threshold": {
                "min_threshold": 0.3,
                "max_threshold": 0.95,
                "percentile": 75,
                "min_results": 3,
                "enable_auto_adjust": True,
            },
        }

    async def apply_retrieval_tuning_profile(self, profile, *, validate=True):
        self.applied_profile = profile
        self.applied_validate = validate
        return {"success": True, "runtime_rebuilt": True, "validation_passed": True}


def test_tuning_profile_normalize_clamps_and_drops_unknown_fields():
    manager = RetrievalTuningManager(_FakePlugin())

    normalized = manager.get_persistable_profile(
        {
            "retrieval": {
                "top_k_final": 9999,
                "ppr_alpha": 5,
                "fusion": {"vector_weight": 10, "bm25_weight": 0},
                "vector_pools": {
                    "semantic_weight": 0,
                    "sparse_weight": 0,
                    "graph_weight": 0,
                    "unknown": "drop-me",
                },
                "unknown": "drop-me",
            },
            "threshold": {
                "min_threshold": 0.9,
                "max_threshold": 0.2,
                "unknown": "drop-me",
            },
            "unknown": "drop-me",
        }
    )

    assert normalized["retrieval"]["top_k_final"] == 512
    assert normalized["retrieval"]["ppr_alpha"] == 0.99
    assert normalized["retrieval"]["fusion"]["vector_weight"] == 1.0
    assert "unknown" not in normalized
    assert "unknown" not in normalized["retrieval"]
    assert "unknown" not in normalized["retrieval"]["vector_pools"]
    assert normalized["threshold"]["min_threshold"] == 0.29
    assert normalized["threshold"]["max_threshold"] == 0.95
    assert "enable_auto_adjust" not in normalized["threshold"]


@pytest.mark.asyncio
async def test_apply_best_rejects_unrecommended_task_by_default():
    manager = RetrievalTuningManager(_FakePlugin())
    manager._tasks["task-1"] = RetrievalTuningTaskRecord(
        task_id="task-1",
        status="completed",
        progress=1.0,
        objective="balanced",
        intensity="quick",
        rounds_total=1,
        best_profile=manager.get_profile_snapshot(),
        validation_summary={"recommended": False},
        recommended=False,
    )

    with pytest.raises(ValueError, match="未通过"):
        await manager.apply_best("task-1")


@pytest.mark.asyncio
async def test_apply_profile_uses_runtime_hot_rebuild_hook():
    plugin = _FakePlugin()
    manager = RetrievalTuningManager(plugin)

    result = await manager.apply_profile({"retrieval": {"top_k_final": 12}}, validate=False)

    assert result["runtime_rebuilt"] is True
    assert result["validation_passed"] is True
    assert plugin.applied_validate is False
    assert plugin.applied_profile["retrieval"]["top_k_final"] == 12


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected_hashes", "returned_hashes", "top_k", "p1", "hit3", "hitk", "mrr", "empty_rate"),
    [
        (["relation", "paragraph"], ["paragraph"], 5, 1, 1, 1, 1, 0),
        (["relation", "paragraph"], ["relation", "relation", "paragraph"], 5, 1, 1, 1, 1, 0),
        (["paragraph"], ["noise", "noise", "noise", "paragraph"], 4, 0, 0, 1, 0.25, 0),
        (["paragraph"], ["noise", "noise", "noise", "paragraph"], 3, 0, 0, 0, 0, 0),
        (["paragraph"], [], 5, 0, 0, 0, 0, 1),
        ([], [], 5, 0, 0, 0, 0, 1),
        ([], ["unlabelled"], 5, 0, 0, 0, 0, 0),
    ],
)
async def test_evaluation_counts_alternative_targets_as_hits(
    monkeypatch, tmp_path, expected_hashes, returned_hashes, top_k, p1, hit3, hitk, mrr, empty_rate
):
    monkeypatch.setattr(tuning_module, "artifacts_root", lambda: tmp_path)
    runtime = SimpleNamespace(ready=True, retriever=object(), threshold_filter=None)
    monkeypatch.setattr(tuning_module, "build_search_runtime", lambda **kwargs: runtime)
    execution = SimpleNamespace(
        success=True,
        results=[SimpleNamespace(hash_value=value) for value in returned_hashes],
        elapsed_ms=1.0,
    )
    monkeypatch.setattr(tuning_module.SearchExecutionService, "execute", AsyncMock(return_value=execution))
    manager = RetrievalTuningManager(_FakePlugin())

    result = await manager._evaluate_profile(
        profile=manager.get_profile_snapshot(),
        cases=[RetrievalQueryCase("case-1", "query_nl", "现居哪里", expected_hashes)],
        objective="balanced",
        top_k_eval=top_k,
        query_timeout_s=1.0,
    )

    metrics = result["metrics"]
    assert metrics["precision_at_1"] == p1
    assert metrics["hit_at_3"] == hit3
    assert metrics["hit_at_k"] == hitk
    assert metrics["mrr"] == mrr
    assert metrics["empty_rate"] == empty_rate
    assert "precision_at_3" not in metrics
    assert "recall_at_k" not in metrics


@pytest.mark.parametrize("objective", ["precision_priority", "balanced", "recall_priority"])
def test_score_preserves_hit_weights_and_zero_empty_rate(monkeypatch, tmp_path, objective):
    monkeypatch.setattr(tuning_module, "artifacts_root", lambda: tmp_path)
    manager = RetrievalTuningManager(_FakePlugin())
    metrics = {
        "precision_at_1": 1.0,
        "hit_at_3": 1.0,
        "hit_at_k": 1.0,
        "mrr": 1.0,
        "spo_relation_hit_rate": 1.0,
        "empty_rate": 0.0,
    }

    assert manager._score_metrics(metrics, objective=objective) == pytest.approx(1.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("baseline_empty,best_empty,recommended", [(0.0, 0.1, False), (0.1, 0.0, True)])
async def test_validation_compares_zero_empty_rate(monkeypatch, tmp_path, baseline_empty, best_empty, recommended):
    monkeypatch.setattr(tuning_module, "artifacts_root", lambda: tmp_path)
    manager = RetrievalTuningManager(_FakePlugin())
    baseline = {
        "score": 0.7,
        "metrics": {"precision_at_1": 1.0, "hit_at_k": 1.0, "empty_rate": baseline_empty, "avg_elapsed_ms": 1.0},
    }
    best = {
        "score": 0.8,
        "metrics": {"precision_at_1": 1.0, "hit_at_k": 1.0, "empty_rate": best_empty, "avg_elapsed_ms": 1.0},
    }
    monkeypatch.setattr(manager, "_evaluate_profile", AsyncMock(side_effect=[baseline, best, baseline, best]))

    result = await manager._validate_best_profile(
        baseline_profile={},
        candidate_profile={},
        holdout_cases=[RetrievalQueryCase("case-1", "query_nl", "现居哪里", ["paragraph"])],
        objective="balanced",
        top_k_eval=5,
        query_timeout_s=1.0,
    )

    assert result["recommended"] is recommended
    assert result["checks"]["empty_rate_ok"] is recommended
    assert result["checks"]["hit_at_k_drop_ok"] is True
    assert result["deltas"]["empty_rate"] == pytest.approx(best_empty - baseline_empty)
