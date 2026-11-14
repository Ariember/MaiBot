from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from src.A_memorix.core.runtime.sdk_memory_kernel import SDKMemoryKernel
from src.A_memorix.core.runtime.services import correction_admin_service
from src.A_memorix.core.storage import GraphStore, MetadataStore


@pytest.fixture
def correction_kernel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    kernel = SDKMemoryKernel(plugin_root=tmp_path, config={"storage": {"data_dir": str(tmp_path)}})
    metadata = MetadataStore(data_dir=tmp_path / "metadata")
    metadata.connect()
    kernel.metadata_store = metadata
    monkeypatch.setattr(kernel, "initialize", AsyncMock())
    monkeypatch.setattr(kernel, "search_memory", AsyncMock(side_effect=AssertionError("多选预览不应重新搜索")))
    monkeypatch.setattr(correction_admin_service, "fuzzy_modify_cfg_enabled", lambda: True)
    monkeypatch.setattr(correction_admin_service, "fuzzy_modify_cfg_allow_global_scope", lambda: False)
    monkeypatch.setattr(correction_admin_service, "fuzzy_modify_cfg_max_targets", lambda: 3)
    monkeypatch.setattr(correction_admin_service, "fuzzy_modify_cfg_candidate_limit", lambda: 6)
    yield kernel
    metadata.close()


@pytest.mark.asyncio
async def test_selected_preview_reads_exact_records_and_still_requires_confirmation(
    correction_kernel: SDKMemoryKernel, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = correction_kernel
    metadata = kernel.metadata_store
    first = metadata.add_paragraph(content="小明喜欢咖啡", source="test")
    unrelated = metadata.add_paragraph(content="小明喜欢红茶", source="test")
    relation = metadata.add_relation("小明", "喜欢", "咖啡")
    captured: Dict[str, Any] = {}

    async def make_plan(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return {
            "confidence": 0.9,
            "operations": [
                {"action": "mark_superseded", "candidate_id": item["candidate_id"]} for item in kwargs["candidates"]
            ]
            + [{"action": "mark_superseded", "hash": unrelated}],
        }

    monkeypatch.setattr(kernel, "_build_fuzzy_modify_llm_plan", make_plan)
    monkeypatch.setattr(kernel, "_build_fuzzy_modify_cascade_preview", lambda **kwargs: {})
    targets = [{"type": "paragraph", "id": first}, {"type": "relation", "id": relation}]
    result = await kernel.memory_correction_admin(
        action="preview", scope="memory", request_text="小明现在喜欢绿茶", targets=targets, limit=1
    )
    assert result["success"] is True
    assert result["requires_confirmation"] is True
    assert [(item["target_type"], item["hash"]) for item in captured["candidates"]] == [
        ("paragraph", first),
        ("relation", relation),
    ]
    assert captured["candidates"][1]["content"] == "小明 喜欢 咖啡"
    assert {item["hash"] for item in result["preview"]["operations"]} == {first, relation}
    assert result["plan"]["status"] == "awaiting_confirmation"
    assert metadata.get_paragraph(first)["content"] == "小明喜欢咖啡"
    assert metadata.get_relation(relation, include_inactive=False) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["paragraph", "relation"])
@pytest.mark.parametrize("with_images", [False, True])
async def test_correction_execute_and_rollback_persist_graph_without_holding_metadata_lock(
    correction_kernel: SDKMemoryKernel, tmp_path: Path, target_type: str, with_images: bool
) -> None:
    kernel = correction_kernel
    metadata = kernel.metadata_store
    kernel.graph_store = GraphStore(data_dir=tmp_path / "graph")
    paragraph = metadata.add_paragraph("小明喜欢红茶", source="test")
    relation = metadata.add_relation("小明", "喜欢", "红茶", source_paragraph=paragraph)
    targets = {"paragraph": paragraph, "relation": relation}
    occurrence_id = ""
    image_links = {}
    if with_images:
        with metadata.transaction(immediate=True) as connection:
            asset = metadata.upsert_image_asset(
                content_hash="correction-image",
                storage_key="correction.png",
                mime_type="image/png",
                byte_size=10,
                width=1,
                height=1,
                conn=connection,
            )
            occurrence = metadata.upsert_image_occurrence(
                asset_id=asset["asset_id"],
                external_ref="correction:message:0",
                source_kind="chat",
                scope_type="chat",
                chat_id="test-chat",
                conn=connection,
            )
            occurrence_id = occurrence["occurrence_id"]
            for kind, target_id in targets.items():
                image_links[kind] = metadata.upsert_image_memory_link(
                    occurrence_id=occurrence_id,
                    target_type=kind,
                    target_id=target_id,
                    link_kind="fact_evidence",
                    evidence={},
                    conn=connection,
                )["link_id"]
    plan = metadata.create_fuzzy_modify_plan(
        request_text="小明已经不喜欢红茶",
        scope="memory",
        plan={"operations": [{"action": "mark_superseded", "target_type": target_type, "hash": targets[target_type]}]},
    )

    executed = await kernel.memory_correction_admin(action="execute", plan_id=plan["plan_id"], confirmed=True)

    assert executed["success"] is True, executed
    assert executed["plan"]["status"] == "executed"
    assert metadata.get_connection().in_transaction is False
    assert metadata.get_relation(relation, include_inactive=False) is None
    assert kernel.graph_store.num_edges == 0
    remaining_link_ids = {item["link_id"] for item in metadata.list_image_memory_links([occurrence_id])}
    expected_link_ids = {image_links["paragraph"]} if with_images and target_type == "relation" else set()
    assert remaining_link_ids == expected_link_ids

    rolled_back = await kernel.memory_correction_admin(action="rollback", plan_id=plan["plan_id"])

    assert rolled_back["success"] is True, rolled_back
    assert rolled_back["plan"]["status"] == "rolled_back"
    assert metadata.get_connection().in_transaction is False
    assert metadata.get_relation(relation, include_inactive=False) is not None
    assert metadata.get_paragraph(paragraph)["metadata"] == {}
    assert {item["link_id"] for item in metadata.list_image_memory_links([occurrence_id])} == set(image_links.values())
    assert kernel.graph_store.num_edges == 1
    reloaded_graph = GraphStore(data_dir=tmp_path / "graph")
    reloaded_graph.load()
    assert reloaded_graph.num_edges == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["empty", "missing", "entity", "duplicate", "too_many", "protected", "scope"])
async def test_invalid_selected_targets_reject_entire_preview(
    correction_kernel: SDKMemoryKernel, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    kernel = correction_kernel
    relation = kernel.metadata_store.add_relation("小明", "喜欢", "咖啡")
    target = {"type": "relation", "id": relation}
    targets = [target]
    if case == "empty":
        targets = []
    elif case == "missing":
        targets += [{"type": "paragraph", "id": "missing"}]
    elif case == "entity":
        targets = [{"type": "entity", "id": "entity-1"}]
    elif case == "duplicate":
        targets = [target, target]
    elif case == "too_many":
        targets = [target] * 4
    elif case == "protected":
        kernel.metadata_store.protect_relations([relation], is_pinned=True)
    planner = AsyncMock(side_effect=AssertionError("无效目标不应调用模型"))
    monkeypatch.setattr(kernel, "_build_fuzzy_modify_llm_plan", planner)
    result = await kernel.memory_correction_admin(
        action="preview",
        request_text="修改记忆",
        scope="memory",
        targets=targets,
        chat_id="chat-1" if case == "scope" else "",
    )
    assert result["success"] is False
    assert result["error"]
    planner.assert_not_called()
    assert kernel.metadata_store.list_fuzzy_modify_plans() == []
