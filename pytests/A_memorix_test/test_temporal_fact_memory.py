from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import threading

import pytest

from src.A_memorix.core.retrieval.dual_path import DualPathRetriever, TemporalQueryOptions
from src.A_memorix.core.runtime.sdk_memory_kernel import KernelSearchRequest, SDKMemoryKernel
from src.A_memorix.core.storage.metadata_store import MetadataStore
from src.A_memorix.core.utils.summary_importer import _normalize_summary_facts, _summary_event_time
from src.common.async_work import run_sync_work


@pytest.fixture
def store(tmp_path):
    value = MetadataStore(data_dir=tmp_path / "memory")
    value.connect()
    try:
        yield value
    finally:
        value.close()


def add_state(store, text, start, *, previous=None, observed_at=None):
    paragraph = store.add_paragraph(
        content=text,
        source="person_fact:person-a",
        metadata={
            "dedup_managed": True,
            "dedup_phase": "complete",
            "dedup_fact_texts": [text],
            "scope_type": "chat",
            "chat_id": "chat-a",
            "person_ids": ["person-a"],
        },
    )
    claim = store.upsert_fact_claim(
        scope_type="person",
        scope_id="person-a",
        fact_key="residence",
        value_text=text,
        cardinality="single",
        valid_from=start,
        evidence_type="paragraph",
        evidence_id=paragraph,
        supersedes_claim_ids=[previous["claim_id"]] if previous else [],
        observed_at=observed_at,
    )
    return paragraph, claim


def test_summary_preserves_event_dates_without_inventing_dates_for_preferences():
    facts = _normalize_summary_facts(
        [
            {
                "fact_id": "f1",
                "text": "甲在上周去过杭州",
                "time_meta": {
                    "event_time_start": "2026-11-02",
                    "event_time_end": "2026-11-08",
                },
            },
            {"fact_id": "f2", "text": "甲喜欢绿茶", "time_meta": None},
        ]
    )
    assert _summary_event_time(facts) == {
        "event_time_start": datetime(2026, 11, 2).timestamp(),
        "event_time_end": datetime(2026, 11, 8, 23, 59).timestamp(),
    }
    assert facts[1]["time_meta"] == {}
    assert _summary_event_time(facts[1:]) == {}
    with pytest.raises(ValueError, match="event_time_start"):
        _normalize_summary_facts(
            [
                {
                    "fact_id": "bad",
                    "text": "错误日期",
                    "time_meta": {
                        "event_time_start": "2026-11-08",
                        "event_time_end": "2026-11-02",
                    },
                }
            ]
        )


def test_unknown_event_time_is_not_replaced_by_ingest_time(store):
    paragraph = store.add_paragraph(
        content="甲曾经去过杭州",
        source="chat_summary:chat-a",
        metadata={"event_time_unknown": True},
    )
    row = store.get_paragraph(paragraph)
    assert row["event_time_start"] is None
    assert store.query_paragraphs_temporal(start_ts=row["created_at"] - 1, end_ts=row["created_at"] + 1) == []
    retriever = DualPathRetriever.__new__(DualPathRetriever)
    retriever.metadata_store = store
    assert not retriever._is_temporal_match(row, TemporalQueryOptions(time_from=row["created_at"] - 1))


def test_historical_state_uses_validity_and_does_not_revive_retracted_evidence(store):
    old_paragraph, old = add_state(store, "甲住北京", 100.0, observed_at=100.0)
    _, current = add_state(store, "甲住上海", 300.0, previous=old, observed_at=500.0)
    assert store.get_fact_claim(old["claim_id"])["valid_to"] == 300.0
    assert store.project_fact_paragraph(store.get_paragraph(old_paragraph)) is None
    historical = store.query_paragraphs_temporal(start_ts=200.0, end_ts=250.0)
    assert [row["hash"] for row in historical] == [old_paragraph]
    row = store.project_fact_paragraph(historical[0], time_from=200.0, time_to=250.0)
    assert row["content"] == "甲住北京"
    assert row["active_fact_claim_ids"] == [old["claim_id"]]
    retriever = DualPathRetriever.__new__(DualPathRetriever)
    retriever.metadata_store = store
    assert retriever._is_temporal_match(historical[0], TemporalQueryOptions(time_from=200.0, time_to=250.0))
    assert not retriever._is_temporal_match(historical[0], TemporalQueryOptions(time_from=300.0, time_to=400.0))
    store.retract_fact_claim(old["claim_id"], reason="信息错误")
    assert store.project_fact_paragraph(historical[0], time_from=200.0, time_to=250.0) is None
    assert store.get_fact_claim(current["claim_id"])["status"] == "active"


def test_future_change_keeps_current_fact_until_it_takes_effect(store):
    now = datetime.now().timestamp()
    old_paragraph, old = add_state(store, "甲住北京", now - 3600)
    new_paragraph, _ = add_state(store, "甲住上海", now + 3600, previous=old)
    assert store.project_fact_paragraph(store.get_paragraph(old_paragraph))["content"] == "甲住北京"
    assert store.project_fact_paragraph(store.get_paragraph(new_paragraph)) is None
    assert [row["value_text"] for row in store.list_current_person_fact_claims("person-a")] == ["甲住北京"]
    assert [
        row["value_text"]
        for row in store.list_current_person_fact_claims(
            "person-a",
            effective_at=now + 7200,
        )
    ] == ["甲住上海"]


def test_replacement_preserves_retracted_status_and_shortens_existing_expiry(store):
    old_paragraph, old = add_state(store, "甲住北京", 100.0, observed_at=100.0)
    with store.transaction() as connection:
        connection.execute("UPDATE fact_claims SET valid_to=500 WHERE claim_id=?", (old["claim_id"],))
    _, replacement = add_state(store, "甲住上海", 300.0, previous=old, observed_at=350.0)
    assert store.get_fact_claim(old["claim_id"])["valid_to"] == 300.0
    store.retract_fact_claim(replacement["claim_id"], reason="信息错误")
    add_state(store, "甲住成都", 400.0, previous=replacement, observed_at=450.0)
    assert store.get_fact_claim(replacement["claim_id"])["status"] == "retracted"
    assert store.query_paragraphs_temporal(start_ts=350.0, end_ts=360.0) == []
    assert store.project_fact_paragraph(store.get_paragraph(old_paragraph), time_from=350.0, time_to=360.0) is None


def test_mixed_event_summary_projects_only_facts_in_requested_period(store):
    early, late = "甲一月去杭州", "乙三月去北京"
    paragraph = store.add_paragraph(
        content=f"{early}\n{late}",
        source="chat_summary:chat-a",
        metadata={
            "dedup_managed": True,
            "dedup_phase": "complete",
            "dedup_fact_texts": [early, late],
            "fact_event_times": {
                early: {"event_time_start": 100.0, "event_time_end": 110.0},
                late: {"event_time_start": 300.0, "event_time_end": 310.0},
            },
        },
        time_meta={"event_time_start": 100.0, "event_time_end": 310.0},
    )
    for index, text in enumerate((early, late)):
        store.upsert_fact_claim(
            scope_type="chat",
            scope_id="chat-a",
            fact_key=f"event-{index}",
            value_text=text,
            evidence_type="paragraph",
            evidence_id=paragraph,
        )
    row = store.get_paragraph(paragraph)
    assert store.project_fact_paragraph(row, time_from=100.0, time_to=120.0)["content"] == early
    assert store.project_fact_paragraph(row, time_from=200.0, time_to=220.0) is None


@pytest.mark.asyncio
async def test_sdk_historical_query_keeps_scope_and_runs_database_filters_off_loop(store, tmp_path, monkeypatch):
    start = datetime(2026, 1, 1).timestamp()
    end = datetime(2026, 7, 1).timestamp()
    old_paragraph, old = add_state(store, "甲住北京", start)
    add_state(store, "甲住上海", end, previous=old)
    other = store.add_paragraph(
        content="其他群的秘密",
        source="chat_summary:chat-b",
        metadata={"chat_id": "chat-b"},
        time_meta={"event_time": datetime(2026, 3, 1).timestamp()},
    )
    kernel = SDKMemoryKernel(
        plugin_root=tmp_path,
        config={
            "retrieval": {
                "search": {
                    "smart_fallback": {"enabled": False},
                    "safe_content_dedup": {"enabled": False},
                }
            }
        },
    )
    kernel.initialize = AsyncMock()
    kernel._initialized = True
    kernel.metadata_store = store
    kernel.graph_store = kernel.vector_store = kernel.embedding_manager = object()
    kernel.episode_retriever = kernel.aggregate_query_service = object()
    kernel.threshold_filter = None
    retriever = DualPathRetriever.__new__(DualPathRetriever)
    retriever.metadata_store = store

    async def retrieve(*, query, top_k, temporal, scope=None, **kwargs):
        assert old_paragraph in scope.paragraph_ids
        rows = await run_sync_work(retriever._retrieve_temporal_only, temporal, top_k, scope)
        assert [row.hash_value for row in rows] == [old_paragraph]
        return rows

    kernel.retriever = SimpleNamespace(retrieve=retrieve)
    main_thread = threading.get_ident()
    query_threads = []
    query = store.query

    def record_query(*args, **kwargs):
        query_threads.append(threading.get_ident())
        return query(*args, **kwargs)

    monkeypatch.setattr(store, "query", record_query)
    result = await kernel.search_memory(
        KernelSearchRequest(
            mode="time",
            query="",
            chat_id="chat-a",
            time_start="2026/03/01",
            time_end="2026/03/31",
            limit=5,
        )
    )
    assert not result.get("error")
    assert [(hit["hash"], hit["content"]) for hit in result["hits"]] == [(old_paragraph, "甲住北京")]
    assert other not in {hit["hash"] for hit in result["hits"]}
    assert query_threads and all(thread != main_thread for thread in query_threads)
