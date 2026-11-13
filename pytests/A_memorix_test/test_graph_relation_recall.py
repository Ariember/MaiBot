from pathlib import Path
from typing import List

import pytest

from src.A_memorix.core.retrieval.graph_relation_recall import GraphRelationRecallService
from src.A_memorix.core.storage.graph_store import GraphStore
from src.A_memorix.core.storage.metadata_store import MetadataStore


def test_count_paragraphs_by_relation_matches_loaded_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = MetadataStore(data_dir=tmp_path)
    store.connect()
    try:
        empty = store.add_relation("Alice", "喜欢", "咖啡")
        shared = store.add_paragraph("Alice 和 Bob 喜欢地图", metadata={"topic": "地图"})
        deleted = store.add_paragraph("Alice 收藏地图", metadata={"topic": "旅行"})
        alice = store.add_relation("Alice", "喜欢", "地图", source_paragraph=shared)
        bob = store.add_relation("Bob", "喜欢", "地图", source_paragraph=shared)
        store.link_paragraph_relation(deleted, alice)
        store.link_paragraph_relation(shared, alice)
        assert store.mark_as_deleted([deleted], "paragraph", reason="test") == 1

        expected = {empty: 0, alice: 2, bob: 1, "missing": 0}
        for relation_hash, count in expected.items():
            assert len(store.get_paragraphs_by_relation(relation_hash)) == count

        def fail_decode(*args):
            pytest.fail("Counting support must not load or decode paragraph rows")

        monkeypatch.setattr(store, "_row_to_dict", fail_decode)
        for relation_hash, count in expected.items():
            assert store.count_paragraphs_by_relation(relation_hash) == count
    finally:
        store.close()


@pytest.mark.parametrize("seeds", [["Alice"], ["Alice", "地图"]])
def test_recall_count_preserves_candidate_payloads_and_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seeds: List[str]
) -> None:
    store = MetadataStore(data_dir=tmp_path)
    store.connect()
    try:
        shared = store.add_paragraph("Alice 喜欢也收藏地图", metadata={"topic": "地图"})
        deleted = store.add_paragraph("Alice 去年收藏地图", metadata={"topic": "旅行"})
        graph = GraphStore()
        for predicate in ["喜欢", "收藏", "绘制", "丢弃"]:
            relation_hash = store.add_relation("Alice", predicate, "地图", confidence=0.7)
            graph.add_edges([("Alice", "地图")], relation_hashes=[relation_hash])
            if predicate in {"喜欢", "收藏"}:
                store.link_paragraph_relation(shared, relation_hash)
            if predicate == "收藏":
                store.link_paragraph_relation(deleted, relation_hash)
            if predicate == "丢弃":
                with store.transaction() as connection:
                    connection.execute("UPDATE relations SET is_inactive = 1 WHERE hash = ?", (relation_hash,))
        store.mark_as_deleted([deleted], "paragraph", reason="test")
        service = GraphRelationRecallService(graph_store=graph, metadata_store=store)

        with monkeypatch.context() as patch:
            patch.setattr(
                store,
                "count_paragraphs_by_relation",
                lambda relation_hash: len(store.get_paragraphs_by_relation(relation_hash)),
            )
            expected = [candidate.to_payload() for candidate in service.recall(seed_entities=seeds)]

        def fail_load(*args):
            pytest.fail("Graph relation recall must not load supporting paragraphs")

        monkeypatch.setattr(store, "get_paragraphs_by_relation", fail_load)
        actual = [candidate.to_payload() for candidate in service.recall(seed_entities=seeds)]

        assert actual == expected
        assert len(actual) == 3
        assert [item["hash"] for item in actual] == sorted(item["hash"] for item in actual)
        assert {item["predicate"]: item["supporting_paragraph_count"] for item in actual} == {
            "喜欢": 1,
            "收藏": 2,
            "绘制": 0,
        }
    finally:
        store.close()
